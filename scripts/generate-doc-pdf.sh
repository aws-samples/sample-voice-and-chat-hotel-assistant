#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0


set -e

# must be run from project root
if [ ! -f "pnpm-lock.yaml" ]; then
    echo "Must be run from project root"
    exit 1
fi

# takes one argument, the output pdf filename
if [ $# -ne 1 ]; then
    echo "Usage: $0 <output.pdf>"
    exit 1
fi
# validate that output is pdf
if [[ $1 != *.pdf ]]; then
    echo "Output must be a pdf file"
    exit 1
fi

export MERMAID_FILTER_FORMAT=pdf

pandoc --metadata title="Hotel Assistant - Multi-Modal Guest Services Platform" \
  --pdf-engine=xelatex \
  -V geometry:margin=1in -V colorlinks=true -V linkcolor=blue -V toccolor=gray -V urlcolor=blue \
  -V mainfont="Amazon Ember Display" -V monofont="Andale Mono" \
  -F mermaid-filter -f markdown-implicit_figures -f markdown+rebase_relative_paths --file-scope \
  --number-sections --toc --toc-depth=2 -s \
  -H scripts/headers.tex \
  README.md \
  documentation/architecture.md \
  documentation/technical_approach.md \
  documentation/message-processing.md \
  documentation/security.md \
  documentation/improvements.md \
  documentation/industry-adaptation.md \
  packages/virtual-assistant/virtual-assistant-chat/README.md \
  packages/virtual-assistant/virtual-assistant-livekit/README.md \
  packages/hotel-pms-simulation/README.md \
  packages/infra/README.md \
  -o $1
