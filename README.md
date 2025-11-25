# Data Asset Manager
### data-asset-manager
Data comes in all shapes and sizes. Data Asset Manger does all the heavy lifting when it comes to simple management 
tasks in Pandas. Once a Blob object is instantiated, using a simple dictionary of configuration settings, tasks like 
reading/writing, sorting and deduplicating, can all be performed with a basic command.

Version 3 has added the ability to read Parquet files using either Pandas or DuckDB. 

We've also introduced connectors for name and address enhancement:
If you have access to the AFD Refiner API service, you can reformat your addresses to the PAF standard, to improve 
matching and postal deliverability.

Basic deduplication routines can now be run at either address or name and address level right in the Blob

## The Blob Class
At the core of Data Asset Manager, is the Blob. Essentially a wrapper for a Pandas DateFrame, the Blob simplifies many of the processes used on address-based datasets. Since the introduction of the [Refiner API](#refiner_section) function in version 3, UK address data can be standardised before merging, matching or deduplicating between non-similar layouts, with much simpler function calls.

## The Config Class
Generally instatiated as the *ini* object, the **Config** class is intended to hold all global variables, including application 
settings and runtime specific variables, such as file names and data structures.
#### job-specs
In the base Config class, job_specs is an empty dict. To create a Blob object, you will need to add the following values:- 
- Description - str: an internal description of the data 
- FileName - str: file name with extension
- Separator - str: delimeter char(s), eg ','
- Columns - list of str: column names
- AddressFields - list of str: names of columns containing address data
- Volatile - bool: if a file is non-volatile, it may be locked against certain operations
- IndexColumn - str: the name of the index column
- Header - int: zero based index of the the header row
- StatisticsColumns - list of str: column names uses for statistical and sorting purposes 
- Location - str: the full unc path to the parent folder of the file

<a id="refiner_section"></a>
## Refiner API
__[AFD Software](https://www.afd.co.uk/)__ are experts in address, bank and contact data validation, delivering tailored software solutions to a wide range of clients. Their mantra is that maintaining a clean, duplicate-free cntact database underpins the foundations of effective marketing and customer service. Among their suite of solutions is an API service that searches and retrieves addresses from large address databases such as the Royal Mail’s Postcode Address File (PAF). It also provides access to the full range of data validation services including email validation, phone validation, bank validation and name validation.
