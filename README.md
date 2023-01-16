# rmscene

Python library to read v6 files from reMarkable tables (software version 3).

In particular, this version introduces the ability to include text as well as drawn lines. Extracting this text is the original motivation to develop this library, but it also can read much of the other types of data in the reMarkable files.

Includes some experimental command line tools to dump block structure and text content:

``` shellsession
$ python -m rmscene print-text file.rm

$ python -m rmscene print-blocks file.rm
```


# operation

Test the parser:
``` shellsession
$ python -m src.rmscene print-blocks page_file.rm
```

Convert a .rm file into an SVG file.
``` shellsession
$ python -m src.rmscene rm2svg tests/rm/dot.stroke.rm /tmp/foo.svg
```

```

## Acknowledgements

https://github.com/ddvk/reader helped a lot in figuring out the structure and meaning of the files.
