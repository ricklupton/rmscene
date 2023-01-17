
all: none


svg: tests/rm/*rm
	@for file in $^ ; do \
		echo $${file} -> tests/svg/$$(basename $${file%.rm}).svg ; \
		python -m src.rmscene rm2svg $${file} tests/svg/$$(basename $${file%.rm}).svg ; \
	done


pdf: tests/rm/*rm
	@for file in $^ ; do \
		echo $${file} -> tests/pdf/$$(basename $${file%.rm}).pdf ; \
		python -m src.rmscene rm2pdf $${file} tests/pdf/$$(basename $${file%.rm}).pdf ; \
	done

