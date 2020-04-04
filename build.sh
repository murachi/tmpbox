#!/bin/sh
npx sass scss/:src/static/
npx tsc
npx typedoc
\cp -f node_modules/zxcvbn/dist/zxcvbn.* src/static/
