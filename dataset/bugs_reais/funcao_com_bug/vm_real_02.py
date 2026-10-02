class Schema:
    def validate(self, data):
        s = self._schema
        e = self._error
        if type(s) in (list, tuple, set, frozenset):
            data = Schema(type(s), error=e).validate(data)
            return type(s)(Or(*s, error=e).validate(d) for d in data)
        if type(s) is dict:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()
            x = None
            coverage = set()  # non-optional schema keys that were matched
            for key, value in data.items():
                valid = False
                for skey, svalue in s.items():
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                        try:
                            nvalue = Schema(svalue, error=e).validate(value)
                        except SchemaError as x:
                            raise
                    except SchemaError:
                        pass
                    else:
                        coverage.add(skey)
                        valid = True
                        break
                if valid:
                    new[nkey] = nvalue
                elif type(skey) is not Optional:
                    if x is not None:
                        raise SchemaError(['key %r is required' % key] +
                                          x.autos, [e] + x.errors)
                    else:
                        raise SchemaError('key %r is required' % key, e)
            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaError('missed keys %r' % (required - coverage), e)
            if len(new) != len(data):
                raise SchemaError('wrong keys %r in %r' % (new, data), e)
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                 self._error)
        if type(s) is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e)
        if callable(s):
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error)
            raise SchemaError('%s(%r) should evalutate to True' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)
