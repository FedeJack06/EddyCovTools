Python tools to analyze and filter high sampling rate Sonic Anemometer and Thermohygrometer measurements.
Designed for measurement campaigns.

A clean way to build a database directly from station raw files.
Graph to look at your data while measurements are being recorded. 

If you are using a Campbell datalogger, you can convert Campbell TOB3 file, thanks to <a href="https://github.com/spirrobe/campbell" target="_blank">spirrobe/campbell</a> repo.

It will contain despiking method and rotation-to-streamline methods.

It is available as PyPi package under name EddyCovTools
Install using
```bash
python3 -m pip install EddyCovTools
```

This repo is a work in progress.

Required:
- python 3
- matplotlib
- pandas
- numpy
- duckdb
- natsort
- campbell-files