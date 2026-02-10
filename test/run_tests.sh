#!/bin/bash

# Ensure results directory exists
mkdir -p results/test

# Create coverage configuration
cat >.coveragerc <<EOF
[run]
source = ../pygfa
omit = 
    /usr/*
    */site-packages/*
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:

[html]
directory = results/test/htmlcov
EOF

# Run tests with coverage to results/test/
echo "Running tests with pytest..."
python -m pytest test/ \
	--junit-xml=results/test/junit.xml \
	--html=results/test/report.html \
	--self-contained-html \
	--cov=pygfa \
	--cov-report=html:results/test/htmlcov \
	--cov-report=xml:results/test/coverage.xml \
	--tb=short

echo "Test results available in results/test/"
echo "Coverage report: results/test/htmlcov/index.html"
echo "Test report: results/test/report.html"
