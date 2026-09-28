class tqdm:
    @staticmethod
    def format_meter(bar_format: str, l_bar: str, r_bar: str) -> str:
        """Reduced from tqdm/_tqdm.py, pre-fix.

        The real code splits a custom format into user-provided halves, then
        mistakenly formats the stale default l_bar/r_bar variables.
        """
        bar_args = {}
        l_bar_user, r_bar_user = bar_format.split('{bar}')
        l_bar, r_bar = l_bar.format(**bar_args), r_bar.format(**bar_args)
        return l_bar + r_bar
