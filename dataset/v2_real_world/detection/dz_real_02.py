class ExactLanguageSearch:
    def choose_best_split(self, possible_parsed_splits, possible_substrings_splits):
        rating = []
        for i in range(len(possible_parsed_splits)):
            num_substrings = len(possible_substrings_splits[i])
            num_substrings_without_digits = 0
            not_parsed = 0
            for j, item in enumerate(possible_parsed_splits[i]):
                if item['date_obj'] is None:
                    not_parsed += 1
                if not any(char.isdigit() for char in possible_substrings_splits[i][j]):
                    num_substrings_without_digits += 1
            rating.append([
                num_substrings,
                0 if not_parsed == 0 else (float(not_parsed)/float(num_substrings)),
                0 if num_substrings_without_digits == 0 else (
                    float(num_substrings_without_digits)/float(num_substrings))])
            best_index, best_rating = min(enumerate(rating), key=lambda p: (p[1][1], p[1][0], p[1][2]))
        return possible_parsed_splits[best_index], possible_substrings_splits[best_index]
