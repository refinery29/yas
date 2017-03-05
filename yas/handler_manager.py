import imp
import inspect
import sys

from yas import YasHandler, NotAHandler, HandlerError
from yas.logging import logger, log


def import_from_dotted_path(dotted_names, path=None):
    """ import_from_dotted_path('foo.bar') -> from foo import bar; return bar

    This function borrowed from Chase Seibert at
    http://chase-seibert.github.io/blog/2014/04/23/python-imp-examples.html
    """
    next_module, remaining_names = dotted_names.split('.', 1)
    file, pathname, description = imp.find_module(next_module, path)
    module = imp.load_module(next_module, file, pathname, description)

    if hasattr(module, remaining_names):
        return getattr(module, remaining_names)

    if '.' not in remaining_names:
        return module

    return import_from_dotted_path(remaining_names, path=module.__path__)

def get_ancestors(target_class):
    bases = []
    if target_class is not object:
        for base in target_class.__bases__:
            bases.extend(get_ancestors(base))

    bases.extend(target_class.__bases__)
    return bases

def is_handler(test_class):
    logger.log.info(f"Checking if {test_class} is a handler")
    public_methods = [member[0] for member in inspect.getmembers(test_class)
                      if not member[0].startswith('__')]

    test_class_bases = get_ancestors(test_class)
    logger.log.debug(f"{test_class} has bases {test_class_bases}")

    class_derives_yas_handler = str(YasHandler) in [str(base) for base in test_class_bases]
    class_defines_required_methods = 'handle' in public_methods and 'test' in public_methods

    check_or_x = {True: '✔', False: '✘'}

    logger.log.info(f"{check_or_x[class_derives_yas_handler]} {test_class} derives {YasHandler}")
    logger.log.info(f"{check_or_x[class_defines_required_methods]} {test_class} defines required methods")

    return class_derives_yas_handler and class_defines_required_methods

def find_handlers_in_module(handler_module):
    return [handler[1](log=log) for handler in inspect.getmembers(handler_module, inspect.isclass)
            if is_handler(handler[1])]

class HandlerManager:
    def __init__(self, handler_list, debug=False):

        logger.log.info(f"Loading handlers from {handler_list}")

        self.handler_list = []
        for handler_name in handler_list:
            logger.log.info(f"Searching for {handler_name}")
            try:

                handler = import_from_dotted_path(handler_name)
                if type(handler) is type and is_handler(handler):
                    logger.log.info(f"Found handler {handler}.")
                    self.handler_list.append(handler(log=log))
                    continue

                module_handlers = find_handlers_in_module(handler)
                if module_handlers:
                    logger.log.info(f"Found handlers in {handler_name}: {module_handlers}")
                    self.handler_list.extend(module_handlers)
                    continue

                raise NotAHandler(handler_name)

            except Exception as exception:
                logger.log.warn(f'Failed to load handler {handler_name}, caught: {exception}')
                if debug:
                    raise exception

        logger.log.info(f'Loaded handlers: {self.handler_list}')

    def handle(self, data, reply):
        logger.log.info(f"Handling {data['yas_hash']}")
        for handler in self.handler_list:
            logger.log.info(f"Testing {data['yas_hash']} against {handler}")
            if handler.test(data):
                logger.log.info(f"Handling {data['yas_hash']} with {handler}")
                handler.handle(data, reply)
                break
        else:
            logger.log.info(f'No handler found for {data}')
