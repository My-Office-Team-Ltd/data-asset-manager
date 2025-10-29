# Data Asset Manager
### data-asset-manager
Data comes in all shapes and sizes. Data Asset Manger does all the heavy lifting when it comes to simple management 
tasks in Pandas. Once a Blob object is instantiated, using a simple dictionary of configuration settings, tasks like 
reading/writing, sorting and deduplicating, can all be performed with a basic command.

Version 3 has added the ability to read Parquet files using either Pandas or DuckDB. 

We've also introduced connectors for name and address enhancement:
If you have access to the AFD Refiner API service, you can reformat your addresses to the PAF standard, to improve matching and postal deliverability.

Basic deduplication routines can now be run at either address or name and address level right in the Blob
