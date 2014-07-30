from __future__ import unicode_literals
# coding: utf-8

# imports
import os
import datetime
import time
import mimetypes

# django imports
from django.core.files.storage import default_storage
from django.utils.encoding import smart_str

try:
    from django.utils.encoding import smart_text
except ImportError:
    # Backward compatibility for Py2 and Django < 1.5
    from django.utils.encoding import smart_unicode as smart_text

# filebrowser imports
from filebrowser_safe.settings import *
from filebrowser_safe.functions import get_file_type, path_strip, get_directory


class FileListing():
    """
    The FileListing represents a group of FileObjects/FileDirObjects.

    An example::

        from filebrowser.base import FileListing
        filelisting = FileListing(path, sorting_by='date', sorting_order='desc')
        print filelisting.files_listing_total()
        print filelisting.results_listing_total()
        for fileobject in filelisting.files_listing_total():
            print fileobject.filetype

    where path is a relative path to a storage location
    """
    # Four variables to store the length of a listing obtained by various listing methods
    # (updated whenever a particular listing method is called).
    _results_listing_total = None
    _results_walk_total = None
    _results_listing_filtered = None
    _results_walk_total = None

    def __init__(self, path, filter_func=None, sorting_by=None, sorting_order=None, site=None):
        self.path = path
        self.filter_func = filter_func
        self.sorting_by = sorting_by
        self.sorting_order = sorting_order
        if not site:
            from filebrowser.sites import site as default_site
            site = default_site
        self.site = site

    # HELPER METHODS
    # sort_by_attr

    def sort_by_attr(self, seq, attr):
        """
        Sort the sequence of objects by object's attribute

        Arguments:
        seq  - the list or any sequence (including immutable one) of objects to sort.
        attr - the name of attribute to sort by

        Returns:
        the sorted list of objects.
        """
        import operator

        # Use the "Schwartzian transform"
        # Create the auxiliary list of tuples where every i-th tuple has form
        # (seq[i].attr, i, seq[i]) and sort it. The second item of tuple is needed not
        # only to provide stable sorting, but mainly to eliminate comparison of objects
        # (which can be expensive or prohibited) in case of equal attribute values.
        intermed = sorted(zip(map(getattr, seq, (attr,)*len(seq)), range(len(seq)), seq))
        return list(map(operator.getitem, intermed, (-1,) * len(intermed)))

    _is_folder_stored = None
    @property
    def is_folder(self):
        if self._is_folder_stored is None:
            self._is_folder_stored = self.site.storage.isdir(self.path)
        return self._is_folder_stored

    def listing(self):
        "List all files for path"
        if self.is_folder:
            dirs, files = self.site.storage.listdir(self.path)
            return (f for f in dirs + files)
        return []

    def _walk(self, path, filelisting):
        """
        Recursively walks the path and collects all files and
        directories.

        Danger: Symbolic links can create cycles and this function
        ends up in a regression.
        """
        dirs, files = self.site.storage.listdir(path)

        if dirs:
            for d in dirs:
                self._walk(os.path.join(path, d), filelisting)
                filelisting.extend([path_strip(os.path.join(path, d), self.site.directory)])

        if files:
            for f in files:
                filelisting.extend([path_strip(os.path.join(path, f), self.site.directory)])

    def walk(self):
        "Walk all files for path"
        filelisting = []
        if self.is_folder:
            self._walk(self.path, filelisting)
        return filelisting

    # Cached results of files_listing_total (without any filters and sorting applied)
    _fileobjects_total = None

    def files_listing_total(self):
        "Returns FileObjects for all files in listing"
        if self._fileobjects_total is None:
            self._fileobjects_total = []
            for item in self.listing():
                fileobject = FileObject(os.path.join(self.path, item), site=self.site)
                self._fileobjects_total.append(fileobject)

        files = self._fileobjects_total

        if self.sorting_by:
            files = self.sort_by_attr(files, self.sorting_by)
        if self.sorting_order == "desc":
            files.reverse()

        self._results_listing_total = len(files)
        return files

    def files_walk_total(self):
        "Returns FileObjects for all files in walk"
        files = []
        for item in self.walk():
            fileobject = FileObject(os.path.join(self.site.directory, item), site=self.site)
            files.append(fileobject)
        if self.sorting_by:
            files = self.sort_by_attr(files, self.sorting_by)
        if self.sorting_order == "desc":
            files.reverse()
        self._results_walk_total = len(files)
        return files

    def files_listing_filtered(self):
        "Returns FileObjects for filtered files in listing"
        if self.filter_func:
            listing = list(filter(self.filter_func, self.files_listing_total()))
        else:
            listing = self.files_listing_total()
        self._results_listing_filtered = len(listing)
        return listing

    def files_walk_filtered(self):
        "Returns FileObjects for filtered files in walk"
        if self.filter_func:
            listing = list(filter(self.filter_func, self.files_walk_total()))
        else:
            listing = self.files_walk_total()
        self._results_walk_filtered = len(listing)
        return listing

    def results_listing_total(self):
        "Counter: all files"
        if self._results_listing_total is not None:
            return self._results_listing_total
        return len(self.files_listing_total())

    def results_walk_total(self):
        "Counter: all files"
        if self._results_walk_total is not None:
            return self._results_walk_total
        return len(self.files_walk_total())

    def results_listing_filtered(self):
        "Counter: filtered files"
        if self._results_listing_filtered is not None:
            return self._results_listing_filtered
        return len(self.files_listing_filtered())

    def results_walk_filtered(self):
        "Counter: filtered files"
        if self._results_walk_filtered is not None:
            return self._results_walk_filtered
        return len(self.files_walk_filtered())

class FileObject():
    """
    The FileObject represents a file (or directory) on the server.

    An example::

        from filebrowser.base import FileObject

        fileobject = FileObject(path)

    where path is a relative path to a storage location.
    """

    def __init__(self, path):
        self.path = path
        self.head = os.path.dirname(path)
        self.filename = os.path.basename(path)
        self.filename_lower = self.filename.lower()
        self.filename_root, self.extension = os.path.splitext(self.filename)
        self.mimetype = mimetypes.guess_type(self.filename)

    def __str__(self):
        return smart_str(self.path)

    def __unicode__(self):
        return smart_text(self.path)

    @property
    def name(self):
        return self.path

    def __repr__(self):
        return smart_str("<%s: %s>" % (self.__class__.__name__, self or "None"))

    def __len__(self):
        return len(self.path)

    # GENERAL ATTRIBUTES
    _filetype_stored = None

    def _filetype(self):
        if self._filetype_stored != None:
            return self._filetype_stored
        if self.is_folder:
            self._filetype_stored = 'Folder'
        else:
            self._filetype_stored = get_file_type(self.filename)
        return self._filetype_stored
    filetype = property(_filetype)

    _filesize_stored = None

    def _filesize(self):
        if self._filesize_stored != None:
            return self._filesize_stored
        if self.exists():
            self._filesize_stored = default_storage.size(self.path)
            return self._filesize_stored
        return None
    filesize = property(_filesize)

    _date_stored = None

    def _date(self):
        if self._date_stored != None:
            return self._date_stored
        if self.exists():
            self._date_stored = time.mktime(default_storage.modified_time(self.path).timetuple())
            return self._date_stored
        return None
    date = property(_date)

    def _datetime(self):
        if self.date:
            return datetime.datetime.fromtimestamp(self.date)
        return None
    datetime = property(_datetime)

    _exists_stored = None

    def exists(self):
        if self._exists_stored == None:
            self._exists_stored = default_storage.exists(self.path)
        return self._exists_stored

    # PATH/URL ATTRIBUTES

    def _path_relative_directory(self):
        "path relative to the path returned by get_directory()"
        return path_strip(self.path, get_directory()).lstrip("/")
    path_relative_directory = property(_path_relative_directory)

    def _url(self):
        return default_storage.url(self.path)
    url = property(_url)

    # FOLDER ATTRIBUTES

    def _directory(self):
        return path_strip(self.path, get_directory())
    directory = property(_directory)

    def _folder(self):
        return os.path.dirname(path_strip(os.path.join(self.head, ''), get_directory()))
    folder = property(_folder)

    _is_folder_stored = None

    def _is_folder(self):
        if self._is_folder_stored == None:
            self._is_folder_stored = default_storage.isdir(self.path)
        return self._is_folder_stored
    is_folder = property(_is_folder)

    def _is_empty(self):
        if self.is_folder:
            try:
                dirs, files = default_storage.listdir(self.path)
            except UnicodeDecodeError:
                from mezzanine.core.exceptions import FileSystemEncodingChanged
                raise FileSystemEncodingChanged()
            if not dirs and not files:
                return True
        return False
    is_empty = property(_is_empty)

    def delete(self):
        if self.is_folder:
            default_storage.rmtree(self.path)
            # shutil.rmtree(self.path)
        else:
            default_storage.delete(self.path)

    def delete_versions(self):
        for version in self.versions():
            try:
                default_storage.delete(version)
            except:
                pass

    def delete_admin_versions(self):
        for version in self.admin_versions():
            try:
                default_storage.delete(version)
            except:
                pass
