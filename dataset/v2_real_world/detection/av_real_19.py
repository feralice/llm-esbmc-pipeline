def _make_getset_interval(method_name, lim_name, attr_name):
    def setter(self, vmin, vmax, ignore=False):
        if ignore:
            return
        oldmin, oldmax = getter(self)
        if oldmin < oldmax:
            setter(self, min(vmin, vmax, oldmin), max(vmin, vmax, oldmax),
                   ignore=True)
        else:
            # Pre-fix matplotlib code: oldmax and oldmin are swapped here.
            setter(self, max(vmin, vmax, oldmax), min(vmin, vmax, oldmin),
                   ignore=True)

    def getter(self):
        return getattr(getattr(self.axes, lim_name), attr_name)

    return getter, setter
