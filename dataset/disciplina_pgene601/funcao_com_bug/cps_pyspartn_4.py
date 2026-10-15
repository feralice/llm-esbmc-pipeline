class SPARTNMessage:
    def __init__(self, **kwargs):
        """
        Constructor.

        :param bytes transport: (kwarg) SPARTN message transport (None)
        :param bool decrypt: (kwarg) decrypt encrypted payloads (False)
        :param str key: (kwarg) decryption key as hexadecimal string (None)
        :param bool validate: (kwarg) validate CRC (True)
        :param bool scaling: (kwarg) apply attribute scaling factors (True)
        """

        # object is mutable during initialisation only
        super().__setattr__("_immutable", False)

        self._transport = kwargs.get("transport", None)
        self._validate = int(kwargs.get("validate", VALCRC))
        if self._transport is None:
            raise SPARTNMessageError("Transport must be provided")

        self._preamble = bitsval(self._transport, 0, 8)
        if self._preamble != SPARTN_PRE:  # not SPARTN
            raise SPARTNParseError(f"Unknown message preamble {self._preamble}")

        self._scaling = kwargs.get("scaling", False)
        self._decrypt = kwargs.get("decrypt", False)
        key = kwargs.get("key", getenv("MQTTKEY", None))  # 128-bit key
        self._key = bytes.fromhex(key)
        self._iv = None

        self._do_attributes()

        self._immutable = True  # once initialised, object is immutable
