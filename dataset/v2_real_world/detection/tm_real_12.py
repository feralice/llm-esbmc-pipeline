class S3CopyToTable:
    @property
    def s3_load_path(self):
        """
        Override to return the load path.
        """
        return None

    def run(self):
        """
        If the target table doesn't exist, self.create_table
        will be called to attempt to create the table.
        """
        if not (self.table):
            raise Exception("table need to be specified")

        path = self.s3_load_path()
        connection = self.output().connect()
