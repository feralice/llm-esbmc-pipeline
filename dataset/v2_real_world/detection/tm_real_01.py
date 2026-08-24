def read_conllx(input_data, use_morphology=False, n=0):
    i = 0
    for sent in input_data.strip().split("\n\n"):
        lines = sent.strip().split("\n")
        if lines:
            while lines[0].startswith("#"):
                lines.pop(0)
            tokens = []
            for line in lines:

                parts = line.split("\t")
                id_, word, lemma, pos, tag, morph, head, dep, _1, iob = parts
                if "-" in id_ or "." in id_:
                    continue
                try:
                    id_ = int(id_) - 1
                    head = (int(head) - 1) if head != "0" else id_
                    dep = "ROOT" if dep == "root" else dep
                    tag = pos if tag == "_" else tag
                    tag = tag + "__" + morph if use_morphology else tag
                    iob = iob if iob else "O"
                    tokens.append((id_, word, tag, head, dep, iob))
                except:  # noqa: E722
                    print(line)
                    raise
            tuples = [list(t) for t in zip(*tokens)]
            yield (None, [[tuples, []]])
            i += 1
            if n >= 1 and i >= n:
                break
