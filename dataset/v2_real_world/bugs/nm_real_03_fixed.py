# esbmc: --unwind 100 --timeout 150s
# Fix youtube-dl a020a0dc: limit_length(s) returns None immediately when s is None.
def truncate_title(video_title: str) -> str:
    if video_title is None:
        return video_title
    if len(video_title) > 80 + 3:
        video_title = video_title[:80] + '...'
    return video_title


def main() -> None:
    has_title: bool = nondet_bool()
    video_title: str = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    if not has_title:
        video_title = None
    truncate_title(video_title)


main()
