#!/bin/sh
npx sass scss/:src/static/
npx tsc
npx typedoc
