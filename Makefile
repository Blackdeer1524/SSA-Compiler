.PHONY: graph cfg ir open-graph

INPUT ?= input.txt
DOT_FILE ?= graph.dot
SVG_FILE ?= graph.svg
IR_FILE ?= ir.txt

FLAGS ?= 

cfg:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) $(FLAGS)

graph: cfg
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-O1:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-sccp --disable-licm --disable-dce  $(FLAGS)
	
graph-O1: cfg-O1
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-sccp:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-licm --disable-dce  $(FLAGS)
	
graph-sccp: cfg-sccp
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-dce:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-licm --disable-sccp  $(FLAGS)
	
graph-dce: cfg-dce
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)
	
cfg-no-ssa:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-ssa $(FLAGS)
	
graph-no-ssa: cfg-no-ssa
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

cfg-licm:
	python main.py --input $(INPUT) --dump-cfg-dot $(DOT_FILE) --disable-sccp --disable-dce  $(FLAGS)
	
graph-licm: cfg-licm
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

open-graph: graph
	firefox $(SVG_FILE)

show-dot:
	dot -Tsvg $(DOT_FILE) -o $(SVG_FILE) && firefox $(SVG_FILE)

ir:
	python main.py --input $(INPUT) --dump-ir $(IR_FILE)