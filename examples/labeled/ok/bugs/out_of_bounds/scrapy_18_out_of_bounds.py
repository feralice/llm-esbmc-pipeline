def extract_filename(content_disposition: str) -> str:
    filename = content_disposition.split(";")[1].split("=")[1]
    return filename.strip("\"'")