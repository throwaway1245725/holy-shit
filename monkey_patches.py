import shutil
from pathlib import Path
from typing import Callable, Dict, Mapping, Union

from tinydb.table import Table
from undetected_chromedriver import patcher


def patch_undetected_chromedriver():
    def fetch_package(self):
        """
        Downloads ChromeDriver from source

        :return: path to downloaded file
        """
        zip_name = f"chromedriver_{self.platform_name}.zip"
        if self.is_old_chromedriver:
            download_url = "%s/%s/%s" % (
                self.url_repo,
                self.version_full.vstring,
                zip_name,
            )
        else:
            zip_name = zip_name.replace("_", "-", 1)
            download_url = (
                "https://storage.googleapis.com/chrome-for-testing-public/%s/%s/%s"
            )
            download_url %= (self.version_full.vstring, self.platform_name, zip_name)

        zip_path = Path(self.data_path) / zip_name
        cached_zip_path = zip_path.with_name(f"cached-{zip_path.name}")
        if cached_zip_path.is_file():
            patcher.logger.debug("cached chromedriver detected %s" % cached_zip_path)
            shutil.copyfile(cached_zip_path, zip_path)
            return str(zip_path.absolute())
        patcher.logger.debug("downloading from %s" % download_url)
        return patcher.urlretrieve(download_url)[0]

    patcher.Patcher.fetch_package = fetch_package


def patch_tinydb():

    def _update_table(self, updater: Callable[[Dict[int, Mapping]], None]):
        """
        Perform a table update operation.

        The storage interface used by TinyDB only allows to read/write the
        complete database data, but not modifying only portions of it. Thus,
        to only update portions of the table data, we first perform a read
        operation, perform the update on the table data and then write
        the updated data back to the storage.

        As a further optimization, we don't convert the documents into the
        document class, as the table data will *not* be returned to the user.
        """

        tables = self._storage.read()

        if tables is None:
            # The database is empty
            tables = {}

        try:
            raw_table = tables[self.name]
        except KeyError:
            # The table does not exist yet, so it is empty
            raw_table = {}

        # Convert the document IDs to the document ID class.
        # This is required as the rest of TinyDB expects the document IDs
        # to be an instance of ``self.document_id_class`` but the storage
        # might convert dict keys to strings.
        table = {
            self.document_id_class(doc_id): doc for doc_id, doc in raw_table.items()
        }

        # Perform the table update operation
        updater(table)

        # Convert the document IDs back to strings.
        # This is required as some storages (most notably the JSON file format)
        # don't support IDs other than strings.
        tables[self.name] = {int(doc_id): doc for doc_id, doc in table.items()}

        # Write the newly updated data back to the storage
        self._storage.write(tables)

        # Clear the query cache, as the table contents have changed
        self.clear_cache()

    Table._update_table = _update_table
