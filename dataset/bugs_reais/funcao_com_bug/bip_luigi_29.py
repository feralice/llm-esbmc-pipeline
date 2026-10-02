class Register:
    @classmethod
    def __get_reg(cls):
        """Return all of the registered classes.

        :return:  an ``collections.OrderedDict`` of task_family -> class
        """
        # We have to do this on-demand in case task names have changed later
        # We return this in a topologically sorted list of inheritance: this is useful in some cases (#822)
        reg = OrderedDict()
        for cls in cls._reg:
            if cls.run == NotImplemented:
                continue
            name = cls.task_family

            if name in reg and reg[name] != cls and \
                    reg[name] != cls.AMBIGUOUS_CLASS and \
                    not issubclass(cls, reg[name]):
                # Registering two different classes - this means we can't instantiate them by name
                # The only exception is if one class is a subclass of the other. In that case, we
                # instantiate the most-derived class (this fixes some issues with decorator wrappers).
                reg[name] = cls.AMBIGUOUS_CLASS
            else:
                reg[name] = cls

        return reg
