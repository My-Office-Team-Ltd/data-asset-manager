from io import BytesIO
from log_manager import LogManager
import os
import pandas as pd
from stop_watch import StopWatch
import traceback
from zipfile import ZipFile



class FileSpecError(ValueError):
    err_dict = {'client_id': ['File Header Row Error',
                              'Error found in File Spec. \nExpected ClientId {} but found {}'],
                'col_count': ['Column Mismatch',
                              'The number of columns found does not match the number specified. \nExpected {} columns, but found {}'],
                'fnf_error': ['File Not Found Error',
                            '{}:\n{}'],
                'hdr_row': ['File Header Row Error',
                            'Error found in file header row. \nExpected\n   {} \nbut found\n   {}'],
                'sasin_fields': ['SAS Fields Error',
                               'Error found in SasField definitions. \nExpected {} field names but found {}'],
                'no_data': ['Data Error',
                            'No readable data has been found in {}{}'],
                'data_types': ['Data Type Error',
                               'Expected data types {}\nError found in row {}'],
                'type_check': ['Data Type Validation Error',
                               'Unable to validate data types for Fields {}\nand Types {}'],
                'fld_ren_ne': ['Blob Error',
                               'Field rename: "{}" does not exist in {}'],
                'fld_ren_ae': ['Blob Error',
                               'Field rename: "{}" already exists in {}'],
                'fld_drop': ['Blob Error',
                             'Field delete: "{}" does not exist in {}']}

    def __init__(self, err_vars):
        """
Raise this when there's a file specification error
        :param err_vars:
        """
        self.err_code = err_vars[0]
        self.error = ''
        self.description = ''
        self.expected_value = ''
        self.found_value = ''
        self.set_error(err_vars)

    def __str__(self):
        return '\n'.join(['FileSpecError:', self.error, self.description])

    def set_error(self, err_vars):
        self.expected_value = err_vars[1]
        if self.err_code == 'data_types':
            self.expected_value = '|'.join(self.expected_value)

        self.found_value = err_vars[2]

        err_vals = self.err_dict.get(self.err_code)
        if err_vals:
            self.error = err_vals[0]
            err_str = err_vals[1]
        else:
            self.error = 'UnkownErrorType'
            err_str = 'An unexpected error has been found\n  Error type: ' + self.err_code + '\n  Param 1: 1.  {}\n  Param  2:  {}'
        arg_str = ''
        if len(err_vars) > 3:
            for x in err_vars[3]:
                arg_str += '\n' + x + ': ' + err_vars[3][x]

        self.description = err_str.format(self.expected_value, self.found_value) + arg_str


class Trigger:  # v1.0.1
    def __init__(self):
        """
When the Blob class was created, Pandas had an unexplained habit of calling lambda functions twice on the first row of
a DataFrame. There are many occasions where that is undesirable. This is a simple workaround.
Using:-<br>
    row_no = Trigger()<br>
    self.data_frame[column_name] = self.data_frame.apply(lambda row: function(row, row_no), axis=1)<br>
You can test for row_no.is_first() in your function and skip if True.

        """
        self.first = True

    def is_first(self):
        """
        :return: True if this is the first time we've seen the first row.
        """
        return_val = self.first
        self.first = False
        return return_val


class Config:  # v 3.0.1
    main_specs = {}
    file_path = {}

    # Immutable attributes (cannot be modified after assignment)
    class ImmutableDict(dict):
        def __setitem__(self, key, value):
            raise TypeError("This dictionary is immutable and cannot be changed.")

        def __delitem__(self, key):
            raise TypeError("This dictionary is immutable and cannot be changed.")

        def clear(self):
            raise TypeError("This dictionary is immutable and cannot be cleared.")

        def update(self, *args, **kwargs):
            raise TypeError("This dictionary is immutable and cannot be updated.")

        def pop(self, key, default=None):
            raise TypeError("This dictionary is immutable and cannot be changed.")

        def popitem(self):
            raise TypeError("This dictionary is immutable and cannot be changed.")

        def setdefault(self, key, default=None):
            raise TypeError("This dictionary is immutable and cannot be changed.")

    class ImmutableList(list):
        def __setitem__(self, index, value):
            raise TypeError("This list is immutable and cannot be changed.")

        def __delitem__(self, index):
            raise TypeError("This list is immutable and cannot be deleted.")

        def append(self, value):
            raise TypeError("This list is immutable and cannot be changed.")

        def extend(self, iterable):
            raise TypeError("This list is immutable and cannot be extended.")

        def insert(self, index, value):
            raise TypeError("This list is immutable and cannot be changed.")

        def remove(self, value):
            raise TypeError("This list is immutable and cannot be changed.")

        def pop(self, index=-1):
            raise TypeError("This list is immutable and cannot be changed.")

        def clear(self):
            raise TypeError("This list is immutable and cannot be cleared.")

    def __init__(self, settings=None, settings_file_url=None):
        """
The Config class is a custom object for setting global variables in a way that is more controllable and therefore more
predictable. Usually instantiated as the *ini* object, Config contains both mutable and immutable objects. Immutable
objects prevent devs inadvertently overwriting the value of list or dictionary item, thus averting the classic problem
with global variables. Although they do offer a limited layer of security, they should not be considered secure.
        """
        if settings_file_url:
            import sys
            import importlib
            import pathlib
            file_path = pathlib.Path(settings_file_url)
            sys.path.insert(0, str(file_path.parent))
            global_app_settings = importlib.import_module(file_path.stem)

            # import everything global_app_settings defines into the current namespace
            app_settings = {}
            for name in dir(global_app_settings):
                if not name.startswith("_"):
                    app_settings[name] = getattr(global_app_settings, name)
            self.__APP_SETTINGS = Config.ImmutableDict(app_settings)
        elif isinstance(settings, dict):
            self.__APP_SETTINGS = Config.ImmutableDict(settings)

        self.app_log = LogManager(application_error_log=self.__APP_SETTINGS.get('ApplicationErrorLog'))
        self.api_log = LogManager(application_error_log=self.__APP_SETTINGS.get('ApplicationErrorLog'))

        self.job_specs = {}
        self.verbose_logging = False
        self.multi_threaded_mode = False

        run_mode = self.__APP_SETTINGS.get('AppMode')
        if run_mode == 'development':
            self.verbose_logging = True
            postcode_areas = self.__APP_SETTINGS.get('DevPostcodeAreas')
        elif run_mode == 'testing':
            postcode_areas = self.__APP_SETTINGS.get('TestPostcodeAreas')
        else:
            postcode_areas = self.__APP_SETTINGS.get('PostcodeAreas')
        postcode_area_list = postcode_areas if isinstance(postcode_areas, list) else \
            [j for i in list(postcode_areas[x] for x in postcode_areas) for j in i]

        self._PCA_LIST = Config.ImmutableList(postcode_area_list)
        self._API_SERVERS = Config.ImmutableList(self.set_apis(self.__APP_SETTINGS.get('ApiServerInfo')))


    # Properties to access immutable attributes without allowing modification
    @property
    def api_batch_size(self):
        return self.__APP_SETTINGS.get('ApiBatchSize')

    @property
    def api_retries(self):
        return self.__APP_SETTINGS.get('ApiRetryLimit')

    @property
    def api_servers(self):
        return self._API_SERVERS

    @property
    def application_log(self):
        return os.path.join(self.__APP_SETTINGS.get('ApplicationsFolder'),
                            self.__APP_SETTINGS.get('ApplicationLogsFolder'),
                            self.__APP_SETTINGS.get('ApplicationName') + '.log')

    @property
    def application_path(self):
        return os.path.join(self.__APP_SETTINGS.get('ApplicationsFolder'),
                            self.__APP_SETTINGS.get('AppMode'),
                            self.__APP_SETTINGS.get('ApplicationName)'))

    @property
    def check_row_count(self):
        return self.__APP_SETTINGS.get('FileFormatCheckRowCount')

    @property
    def chunk_size(self):
        return self.__APP_SETTINGS.get('FileIteratorChunkSize')

    @property
    def default_delimiter(self):
        return self.__APP_SETTINGS.get('DefaultDelimiter')

    @property
    def default_output_fields(self):
        return self.__APP_SETTINGS.get('DefaultOutFields')

    @property
    def file_spec_version(self):
        return self.__APP_SETTINGS.get('FileSpecVersion')

    @property
    def index_ext(self):
        return self.__APP_SETTINGS.get('IndexFileExtn')

    @property
    def index_field(self):
        return self.__APP_SETTINGS.get('InternalUidFieldName')

    @property
    def postcode_area_list(self):
        return self._PCA_LIST

    @property
    def refiner_postcode_field(self):
        return self.__APP_SETTINGS.get('RefinerPostcodeField')

    @property
    def refiner_output_fields(self):
        return self.__APP_SETTINGS.get('RefinerOutputFields')

    @property
    def report_chunk_frequency(self):
        return self.__APP_SETTINGS.get('BundleReportFrequency')

    @property
    def segment_folders(self):
        return self.__APP_SETTINGS.get('SegmentFolders')

    @property
    def wf_supply_folder(self):
        return self.__APP_SETTINGS.get('WhenFreshSupplyFolders')

    def set_apis(self, api_server_info, refiner_request_fields=None):
        root = r'http://{}/v1/refiner/GBR/clean?serial={}&password={}'
        multi_threaded_mode = (len(api_server_info) > 1)
        api_servers = []
        for si in api_server_info:
            api_server = ApiServer(si['name'], si['host'], si['licence'], si['password'], root, self.api_log,
                                   multi_threaded_mode, refiner_request_fields, frmt='json')
            if api_server.online:
                api_servers.append(api_server)
        print(f"{len(api_servers)} server{'' if len(api_servers) == 1 else 's'} initialised")
        return api_servers


class Blob:  # v 3.0.1
    idx = None

    def __init__(self, ini, file_type, log: LogManager, name=None, segment=False, file_spec_override=None):
        """
A container for managing Pandas DataFrames
        :param ini: The app_setup module, which stores all the job related variables
        :param file_type: The name of the template to use. (Templates are set in app_setup.py -> main_specs)
        :param log: A LogManager object used for application level logging. (Read/write logging is managed by the
        inbuilt rw_log)
        :param name: A friendly name for the dataset
        :param segment: Not yet implemented
        """
        self.rw_log = LogManager(display=False)
        if ini.verbose_logging:
            self.rw_log.start_text_logging(ini.application_log)
        self.ini = ini
        self.timer = StopWatch()
        self.segment = segment
        self.file_type = file_type
        file_specs = ini.job_specs[file_type]
        # print('*** DataAssetManger.Blob.__init__.file_specs:', file_specs)
        if file_spec_override:
            file_specs = {key: file_spec_override.get(key, val) for key, val in file_specs.items()}
        self.log = log
        # self.log.create_entry([file_specs, name, segment])
        self.data_frame = pd.DataFrame()
        self.header_check_style = 'loose'
        self.loaded = False
        self.processed = False
        self.row_count = 0
        self.index_min = 0
        self.index_max = 0
        self.file_specs = file_specs
        self.name = file_specs['Description'] if name is None else name
        self.display_name = file_type + '|' + self.name
        if self.name == 'Frame':
            self.file_name = 'Name not set'
            self.file_extn = 'csv'
            self.file_path = 'Path not set'
            self.archived_name = 'Archive name not set'
            self.df_fields = 'Fields not set'
            self.url = 'URL not set'
            self.status = 'Empty'
            self.volatile = 'False'
        else:
            self.file_name = file_specs['FileName']
            self.file_extn = file_specs['FileName'].split('.')[-1]
            self.separator = self.get_file_spec('Separator', ini.default_delimiter)
            self.df_fields: dict = file_specs['Columns']
            self.field_names = list(self.df_fields.keys())
            if file_specs['IndexColumn']:
                self.idx = file_specs['IndexColumn']
                for icol in self.idx:
                    if icol in self.field_names:
                        self.field_names.remove(icol)
                # self.field_names = self.field_names[1:]
            self.header = None if int(float(file_specs['Header'])) < 0 else int(float(file_specs['Header']))
            self.file_path = file_specs['Location']
            if segment:
                self.file_path = os.path.join(self.file_path, ini.segment_folders, self.name)
            self.volatile = self.get_file_spec('Volatile', True)
            self.archived_name = self.get_file_spec('ArchivedName', self.file_name)
            # self.data_types = self.df_fields
            # address_fields = self.field_names if file_specs['AddressFields'] == '' else file_specs['AddressFields']
            self.address_fields = self.get_file_spec('AddressFields', self.field_names)
            self.status = 'Instantiated'
            self.url = os.path.join(self.file_path, self.file_name)

    def __repr__(self):
        out_str = '\n==================\nFile Specification\n------------------\n'
        out_str = out_str + f'Name: {self.name}\n'
        out_str = out_str + f'File Name: {self.file_name}\n'
        out_str = out_str + f'File Type: {self.file_type}\n'
        out_str = out_str + f'Field Delimiter: {self.separator}\n'
        out_str = out_str + f'Location: {self.file_path}\n'
        out_str = out_str + f'Archived Name: {self.archived_name}\n'
        out_str = out_str + f'Table Fields:-\n{self.df_fields}\n==================\n'
        if self.loaded:
            out_str += f'Row count: {self.row_count}\n{self.data_frame.iloc[0][self.field_names]}\n\n'
        else:
            out_str += self.name + ' is empty\n\n'

        return out_str

    def get_file_spec(self, spec: str, default_val: object = ''):
        out_val = self.file_specs.get(spec)
        if not out_val or out_val == '':
            out_val = default_val
        return out_val

    def read_file(self, url=None, skiprows=None, rows=None, unicode_escape=False, archive=None):
        # First check to see if we're reading from a compressed folder
        if archive:
            location = archive.get('location')
            zip_name = archive.get('zip_name')
            file_name = archive.get('file_list')
            password = archive.get('password')
            zip_url = str(os.path.join(location, zip_name))

            if not os.path.exists(zip_url):
                msg = ['No file available', zip_url, 'No data loaded into blob']
                self.log.create_entry(msg, new_lines=True)
                return msg
            input_zip = ZipFile(zip_url)
            file_path = zip_url
            file_stream = input_zip.read(file_name, pwd=password)
            read_url = BytesIO(file_stream)
        else:
            read_url = self.url if url is None else url
            file_path = read_url
            if not os.path.exists(file_path):
                msg = ['No file available', file_path, 'No data loaded into blob']
                self.log.create_entry(msg, new_lines=True)
                return msg

        field_names = self.idx.copy() if isinstance(self.idx, list) else [self.idx]
        if self.idx and self.idx[0]:
            field_names.extend(self.field_names)
        else:
            field_names = self.field_names

        try:
            # print('DAM.read_file', self.file_extn)
            if self.file_extn.lower() in ['csv', 'txt', 'tsv', 'idx']:
                if unicode_escape:
                    df = pd.read_csv(read_url, sep=self.separator, header=self.header, names=field_names, nrows=rows, on_bad_lines='warn',#lambda x: x[:len(self.header)],
                                     skiprows=skiprows, dtype=self.df_fields, index_col=self.idx,
                                     encoding='unicode_escape', engine='python')
                else:
                    df = pd.read_csv(read_url, sep=self.separator, header=self.header, names=field_names, nrows=rows, on_bad_lines='warn',#lambda x: x[:len(self.header)], engine='python',
                                     skiprows=skiprows, dtype=self.df_fields, index_col=self.idx,
                                     encoding_errors='ignore')
            elif self.file_extn.lower() in ['xls', 'xlsx']:
                df = pd.read_excel(read_url, nrows=rows, skiprows=skiprows)
            else:
                df = None
            self.load_data(df)
        except KeyError:
            msg = ['Key error', self, 'No data loaded into blob']
            self.log.create_entry(msg, new_lines=True)
            return msg
        except ValueError:
            e = traceback.format_exc()
            msg = ['FileSpec error', self, 'No data loaded into blob']
            self.log.create_entry(msg, new_lines=True)
            self.log.create_entry(e, new_lines=True)
            return msg
        except FileNotFoundError:
            e = traceback.format_exc()
            self.log.create_entry(e, new_lines=True)
            msg = ['Read error', file_path, 'No data loaded into blob']
            self.log.create_entry(msg, new_lines=True)
            return msg

        self.log.create_entry(['Blob Input', self.file_type, self.row_count, file_path])
        self.rw_log.create_entry(['Read', self.file_type, self.name, file_path, self.row_count])
        # return ['File loaded', self, 'Data loaded into blob']
        return self.row_count

    def read_large_file(self, query_str, con=None, source=None, index=None):
        """
For reading files of over 100MB, this option uses duckdb to read the file.
        :param query_str: The query string should contain one pair of curly braces to be replaced by the file path. Alternatively, this can be hard-coded.
        :param con: Table name or full UNC file path. If none is provided, the FileType's url is used.
        :param index: If provided, the index column is used as the DataFrame index.
        """
        def run_query(sql):
            # If caller provided a connection, use it
            if isinstance(con, duckdb.DuckDBPyConnection):
                return con.query(sql).to_df()
            # Otherwise, fall back to the module-level singleton
            return duckdb.query(sql).to_df()

        sql = query_str.format(source)
        if index:
            df = run_query(sql).set_index(index)
        else:
            df = run_query(sql)

        # Remove tab characters from the column names
        df.columns = [c.replace('\t', '') for c in df.columns]
        self.load_data(df)

    def read_parquet_file(self, url=None, reset_columns=False):
        """
        Reads a Parquet file into a pandas DataFrame.
        If reset_columns is True, the column names are for the Blob are reset to match the file's column names.
        Returns an empty DataFrame if the file doesn't exist yet.
        """
        if url is None:
            url = '.'.join(self.url.split('.')[0:-1]) + '.parquet'
        try:
            df = pd.read_parquet(url)
            if reset_columns:
                self.field_names = list(df.columns)
                self.df_fields = df.dtypes
            self.load_data(df)
        except FileNotFoundError:
            msg = ['Read error', url, 'No data loaded into blob', f'Parquet file not found: {url}']
            self.log.create_entry(msg, new_lines=True)
            return pd.DataFrame()
        return df

    def read_zip_file(self, archive: dict, query_str, unicode_escape=False):
        """
For reading files of over 100MB, this option uses duckdb to read the file.
        :param archive: dict containing location, zip_name, file_list, password.
        :param query_str: The query string should contain one pair of curly braces to be replaced by the file path. Alternatively, this can be hard-coded.
        :param url: Full UNC file path. If none is provided, the FileType's url is used.
        :param index: If provided, the index column is used as the DataFrame index.
        """
        location = archive.get('location')
        zip_name = archive.get('zip_name')
        file_name_list = archive.get('file_list')
        password = archive.get('password')
        zip_url = os.path.join(location, zip_name)

        # Read from ZIP entirely in memory
        df_list = []
        with ZipFile(zip_url) as input_zip:
            try:
                # --- Initialize DuckDB connection ---
                con = duckdb.connect()
                for file_name in file_name_list:
                    file_stream = input_zip.read(file_name, pwd=password)
                    encoding = 'utf-8' if not unicode_escape else 'unicode_escape'
                    read_data = StringIO(file_stream.decode(encoding, errors='ignore'))

                    if read_data:
                        # Reset to start of stream each batch
                        read_data.seek(0)

                        # Create a DuckDB relation from the CSV stream
                        rel = con.read_csv(read_data, sep=self.separator, header=self.header)

                        # Register it as a temporary view
                        con.register('input_stream', rel)

                        query = f"""
                            SELECT * 
                            FROM input_stream
                            {query_str}
                        """
                    df_file = con.execute(query).fetchdf()
                    if df_file.empty:
                        break
                    if self.idx:
                        df_file.set_index(self.idx, inplace=True)
                    df_list.append(df_file)
            except Exception as e:
                self.log.create_entry([str(e)], new_lines=True)
            finally:
                # --- Clean up memory before next file ---
                try:
                    if read_data:
                        read_data.close()
                        del read_data
                    if file_stream:
                        del file_stream
                    if con:
                        con.close()
                except Exception:
                    pass  # ignore cleanup errors

                # optional: force garbage collection for large files
                gc.collect()

        if len(df_list) > 1:
            self.load_data(pd.concat(df_list))
        elif len(df_list) == 1:
            self.load_data(df_list[0])

    def file_iterator(self, chunksize, url=None, unicode_escape=False, archive=None):
        try:
            # --- Resolve file source ---
            if archive:
                location = archive.get('location')
                zip_name = archive.get('zip_name')
                file_name = archive.get('file_list')
                password = archive.get('password')
                zip_url = os.path.join(location, zip_name)

                if not os.path.exists(zip_url):
                    msg = ['No file available', zip_url, 'No data loaded into blob']
                    self.log.create_entry(msg, new_lines=True)
                    return msg

                # Read from ZIP entirely in memory
                with ZipFile(zip_url) as input_zip:
                    file_stream = input_zip.read(file_name, pwd=password)
                read_url = BytesIO(file_stream)
                file_path = f'memory_csv_{os.path.basename(file_name)}'
            else:
                read_url = self.url if url is None else url
                file_path = read_url
                if not os.path.exists(file_path):
                    msg = ['No file available', file_path, 'No data loaded into blob']
                    self.log.create_entry(msg, new_lines=True)
                    return msg

            # --- Determine column names ---
            field_names = self.idx.copy() if isinstance(self.idx, list) else [self.idx]
            if self.idx:
                field_names.extend(self.field_names)
            else:
                field_names = self.field_names

            # --- Initialize DuckDB connection ---
            con = duckdb.connect()

            # If it's an in-memory ZIP, register the bytes as a virtual file
            if isinstance(read_url, BytesIO):
                con.register('input_stream', read_url)

            # --- Batch generator ---
            offset = 0
            while True:
                # DuckDB automatically handles both local files and registered in-memory streams
                source = 'input_stream' if isinstance(read_url, BytesIO) else f"'{file_path}'"
                query = f"""
                    SELECT * FROM read_csv_auto({source}, delim='{self.separator}', header={bool(self.header)})
                    LIMIT {chunksize} OFFSET {offset}
                """
                df = con.execute(query).fetchdf()
                if df.empty:
                    break
                if self.idx:
                    df.set_index(self.idx, inplace=True)
                yield df
                offset += chunksize

        except (KeyError, ValueError, FileNotFoundError) as e:
            err = traceback.format_exc()
            msg = [type(e).__name__, self, 'No data loaded']
            self.log.create_entry(msg, new_lines=True)
            self.log.create_entry(err, new_lines=True)
            return msg

    def load_data(self, df, copy=True):
        if df.shape[0] > 0:
            if copy:
                self.data_frame = df.fillna('')
            else:
                self.data_frame = df
                self.data_frame.fillna('', inplace=True)
            self.index_min = self.data_frame.index.min()
            self.row_count = df.shape[0]
            self.index_max = self.data_frame.index.max()
            self.loaded = (self.row_count > 0)
            return self.index_max
        else:
            self.index_min = 0
            self.row_count = 0
            self.index_max = 0
            self.data_frame = pd.DataFrame()
            self.loaded = False
            return 0

    def write_file(self, url=None, out_fields: list = None, mode='w', make_dir=False, backup=False):
        if out_fields is None:
            out_fields = self.field_names
        header = mode == 'w' and self.header is not None
        out_url = self.url if url is None else url
        index = self.idx is not None
        idx_name = None
        if index and self.idx in out_fields:
            idx_name = self.idx
            out_fields.remove(self.idx)
        elif out_fields[0] == 'CallIndex':
            idx_name = out_fields[1]
            self.data_frame.index.rename(idx_name, inplace=True)
            out_fields = out_fields[2:]
            index = True
        if self.data_frame.shape[0] > 0:
            self.log.create_entry(['Blob Output', self.file_type,
                                   self.row_count, out_url])
            if mode == 'w' and backup and os.path.exists(out_url):
                inc = 1
                while os.path.exists(out_url.replace('.', f'_{inc}.')):
                    inc += 1
                os.rename(out_url, out_url.replace('.', f'_{inc}.'))
            if make_dir and url is None and not os.path.exists(self.file_path):
                os.makedirs(self.file_path)
            try:
                self.data_frame.to_csv(out_url, sep=self.separator, columns=out_fields, header=header, index=index,
                                       index_label=idx_name, mode=mode, encoding='utf-8-sig')
            except KeyError as e:
                err_msg = 'WriteError: ' + str(self)
                raise FileSpecError(['fld_drop', e.args[0], self.field_names])
        else:
            self.log.create_entry(['Blob Output', self.file_type, 'No data', out_url])
        self.rw_log.create_entry(['Write', self.file_type, self.name, out_url, self.row_count])

    def write_parquet_file(self, url=None, index=False):
        """
        Writes a pandas DataFrame to a Parquet file, overwriting if it already exists.
        """
        if url is None:
            url = '.'.join(self.url.split('.')[0:-1]) + '.parquet'
        self.data_frame[self.field_names].to_parquet(url, engine="pyarrow", index=index, compression="snappy")
        self.log.create_entry([f"{self.row_count} rows written", url])

    def update_url(self, place_holder=None, var_string=None, file_name=None, file_path=None, permanent=False):
        path = self.file_path if file_path is None else file_path
        name = self.file_name if file_name is None else file_name
        if place_holder is not None:
            path = path.replace(place_holder, var_string)
            name = name.replace(place_holder, var_string)
        out_url = os.path.join(path, name)
        if permanent:
            self.file_path = path
            self.file_name = name
            self.url = out_url
        return out_url

    def copy(self, name=None, file_name=None):
        """
Creates a new empty instance of the blob using the initial file specs.
        :param name: str
        :param file_name: str
        :return: Blob
        """
        new_file = Blob(self.ini, self.file_type, self.log, name=name, segment=self.segment)
        if file_name is not None:
            new_file.update_url(file_name=file_name, permanent=True)
        return new_file

    def clone(self, name=None, file_name=None):
        """
Creates a new instance of the blob using the initial file specs, with a copy of the source DataFrame
        :param name: str
        :param file_name: str
        :return: Blob
        """
        if not file_name:
            file_name = self.file_name
        new_name = self.name if name is None else name
        new_blob = Blob(self.ini, self.file_type, self.log, name=new_name, segment=self.segment)
        new_blob.update_url(file_name=file_name, file_path=self.file_path, permanent=True)
        if self.row_count > 0:
            new_blob.load_data(self.data_frame, copy=True)
        return new_blob

    def merge_data(self, in_data_frames, inc_self=True):
        if isinstance(in_data_frames, list):
            df_list = in_data_frames
            if inc_self and self.loaded:
                df_list.insert(0, self.data_frame)
        else:
            df_list = [self.data_frame, in_data_frames]
        self.load_data(pd.concat(df_list, sort=False))
        return len(df_list)

    def merge_blobs(self, blob_list, inc_self=True):
        if isinstance(blob_list, list):
            df_list = []
            for blob in blob_list:
                if blob.data_frame.shape[0] > 0:
                    df_list.append(blob.data_frame)
                    self.merge_data(df_list, inc_self)
        else:
            self.merge_data(blob_list.data_frame, inc_self)
        return self

    def debug_write(self, file_name_suffix):
        new_url = self.update_url(file_name=self.file_name.replace('.', '_' + file_name_suffix + '.'))
        self.write_file(url=new_url)

    def reset(self, drop=False):
        if drop and self.volatile:
            if os.path.exists(self.url):
                os.remove(self.url)
        self.__init__(self.ini, self.file_type, self.log, name=self.name, segment=self.segment)
        return self

    def reshape(self, new_fields: dict, transform_method=None, inplace=False, **kwargs):
        """
Reshaping a Blob changes the column headings and types in the metadata, it does not change the DataFrame unless
inplace=True
        :param new_fields:
        :param transform_method:
        :param inplace:
        :param kwargs:
        """
        self.df_fields = new_fields
        self.field_names = list(self.df_fields.keys())
        # self.data_types = self.df_fields

        if transform_method:
            self.transform(transform_method, **kwargs)
        elif inplace:
            self.load_data(self.data_frame[self.field_names], copy=True)

    def dedupe(self, columns):
        self.data_frame.drop_duplicates(subset=columns, keep='first', inplace=True)
        self.row_count = self.data_frame.shape[0]

    def purge(self, in_blob, column=None):
        if column is None:
            self.load_data(self.data_frame[~self.data_frame.index.isin(in_blob.data_frame.idx)])
        else:
            self.load_data(self.data_frame[~self.data_frame[column].isin(in_blob.data_frame[column])])

    def filter(self, column, value=None, operand='>'):
        # c = self.row_count
        try:
            if value is None:
                self.load_data(self.data_frame[self.data_frame[column] != ''].copy())
                # self.log.create_entry(['Filtered rows on', column + ' = empty', c, self.row_count])
            else:
                self.load_data(self.data_frame[eval('self.data_frame[column] ' + operand + ' value')].copy())
                # self.log.create_entry(['Filtered rows on', column + ' > ' + str(value), c, self.row_count])
        except TypeError as e:
            err_msg = 'FilterError:'  # + ddf(self.data_frame, column, 10, 10)
            raise Exception(err_msg) from e

    def reindex(self, idx_start):
        self.data_frame.index = range(idx_start, idx_start + self.row_count)

    def sort(self, sort_fields: list = None, sort_order: list = None):
        if sort_fields is None:
            if sort_order is None or len(sort_order) != 1:
                order = True
            else:
                order = sort_order[0]
            self.data_frame.sort_index(ascending=order, inplace=True)
        elif sort_order is not None and len(sort_order) == len(sort_fields):
            self.data_frame.sort_values(by=sort_fields, ascending=sort_order, inplace=True)
        else:
            self.data_frame.sort_values(by=sort_fields, inplace=True)

    def refine_addresses(self, remove_errors=True):
        """
*An AFD Refiner licence is required to use this function.*\n
Parses data through an AFD Refiner API service to enhance addresses in the blob.data_frame. blob.data_frame is updated
to include a UDPRN & UPRN field. If remove_errors is True, only addresses with a valid UDPRN are included in blob.data_frame,
but all rows are returned by this function to allow for further processing.
        :param remove_errors: bool, if True, all rows without a UDPRN are removed from the blob.data_frame
        :return: DataFrame, unfiltered with UDPRN & UPRN added
        """
        t_rows = self.row_count
        df_refiner = check_data_frame(self.ini, self.data_frame, self.address_fields)  # .iloc[0:2000].copy()
        df_merged = df_refiner[['UDPRN', 'UPRN']].merge(
            self.data_frame,
            left_index=True,
            right_index=True,
            how='inner'
        )
        if remove_errors:
            self.load_data(df_merged[df_merged['UDPRN'] != '00000000'].copy())
        else:
            self.load_data(df_merged)
        self.field_names.insert(0, 'UPRN')
        self.field_names.insert(0, 'UDPRN')
        self.df_fields['UDPRN'] = str
        self.df_fields['UPRN'] = str
        self.log.create_entry(['Refiner',
                               f'{t_rows} rows submitted',
                               f"{df_merged[df_merged['UDPRN'] == '00000000'].shape[0]} rows {'dropped' if remove_errors else 'with no UDPRN'}"])
        return df_merged

    def apply(self, function, *args):
        df = self.data_frame.apply(lambda r: function(r, *args), axis=1)
        self.load_data(df)
        return self

    def transform(self, transform_method, **kwargs):
        """
Perform a function as a method.
        :param transform_method: The function to be performed MUST return a DataFrame
        :param kwargs: Any arguments required by the function can be passed as keyword args. Use write=True to
        automatically output the data to the default output file.
        """
        df = transform_method(self.data_frame, **kwargs)
        self.load_data(df)
        if kwargs.get('write'):
            self.write_file()

    def create_column(self, column_name, function=None, data_type='str'):
        """
Adds a new column to the data. If a function is provided, it will be used to populate the DataFrame column. If a
data_type is provided, the default value for that type will be used.
        :param column_name: str
        :param function: function or method to be used on each row, to populate the field
        :param data_type: dtype
        """
        if function:
            fr = Trigger()
            self.data_frame[column_name] = self.data_frame.apply(lambda row: function(row, fr), axis=1)
        else:
            self.field_names.append(column_name)
            self.df_fields[column_name] = data_type
            if data_type == 'int':
                self.data_frame[column_name] = 0
            else:
                self.data_frame[column_name] = ''

    def drop_column(self, column_name):
        """
Removes the passed field from the metadata and the DataFrame
        :param column_name: str
        """
        if column_name not in self.field_names:
            raise FileSpecError(['fld_drop', column_name, self.field_names])

        self.df_fields.pop(column_name)
        self.field_names.remove(column_name)
        if self.loaded and column_name in self.data_frame.columns:
            self.data_frame.drop(columns=column_name, inplace=True)

    def rename_column(self, old_column_name, new_column_name):
        """
Renames a field in both the metadata and the DataFrame. Changing data types is not supported.
        :param old_column_name: str
        :param new_column_name: str
        """
        file_spec = {'New Field Name': new_column_name, 'Name': self.name, 'File Name': self.file_name,
                     'File Type': self.file_type, 'Location': self.file_path, 'Row Count': str(self.row_count),
                     'Table': str(self.data_frame.columns)}
        if old_column_name not in self.field_names:
            raise FileSpecError(['fld_ren_ne', old_column_name, self.field_names, file_spec])

        if new_column_name in self.field_names:
            raise FileSpecError(['fld_ren_ae', old_column_name, self.field_names, file_spec])

        self.df_fields = {new_column_name if k == old_column_name else k: v for k, v in self.df_fields.items()}
        self.field_names = [new_column_name if v == old_column_name else v for v in self.field_names]
        self.data_frame.rename(columns={old_column_name: new_column_name}, inplace=True)

    def df_layout(self, layout_file):
        """
Generates a File Layout in a CSV file, based on the metadata, not the DataFrame
        :param layout_file: The full URL for the output file
        :return:
        """

        def __check_len(field_name):
            try:
                if isinstance(self.data_frame[field_name], str):
                    return str(max(self.data_frame[field_name], key=len))
                else:
                    return 'int'
            except ValueError:
                return 'NULL'

        out_fields = self.df_fields if self.idx == '' else self.df_fields[1:]
        out_fields['MaxLen'] = out_fields.apply(lambda row: __check_len(row['name']), axis=1)
        out_fields.to_csv(layout_file, mode='a', sep='|', header=True, index=True)

        return str(out_fields)

    def html(self):
        out_str = '<table>\n'
        out_str = out_str + '<tr><th colspan=2 style="text-align:left;font-size:1.2em;">' + self.name + '</th></tr>\n'
        out_str = out_str + '<tr><td>File Name:</td><td>' + self.archived_name + '</td></tr>\n'
        out_str = out_str + '<tr><td>Field Names:-</td><td>* See layout tables below</td></tr>\n'
        if self.loaded:
            out_str += '<tr><td>Row count:</td><td>' + '{:,}'.format(self.row_count) + '</td></tr>\n'
        else:
            out_str += '<tr><td colspan=2>' + self.name + ' is empty</td></tr>\n'

        out_str += '</table>\n'
        return out_str

