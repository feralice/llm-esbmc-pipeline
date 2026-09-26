from typing import Optional


def cli_bool_option(params: dict[str, bool], param: str) -> None:
    value: Optional[bool] = params.get(param)
    assert isinstance(value, bool)


cli_bool_option({"verbose": True}, "verbose")
cli_bool_option({}, "verbose")
