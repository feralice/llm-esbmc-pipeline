class Language:
    def remove_pipe(self, name):
        """Remove a component from the pipeline.

        name (unicode): Name of the component to remove.
        RETURNS (tuple): A `(name, component)` tuple of the removed component.

        DOCS: https://spacy.io/api/language#remove_pipe
        """
        if name not in self.pipe_names:
            raise ValueError(Errors.E001.format(name=name, opts=self.pipe_names))
        if ENABLE_PIPELINE_ANALYSIS:
            analyze_all_pipes(self.pipeline)
        return self.pipeline.pop(self.pipe_names.index(name))
