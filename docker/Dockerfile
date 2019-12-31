FROM python:3.9-rc-alpine3.10

RUN apk update \
 && apk upgrade \
 && apk add graphviz ttf-freefont \
 && pip install pyyaml

COPY ./itassets /itassets
COPY run_itassets.py head.html tail.html /itassets/

CMD ["python", "/itassets/run_itassets.py", "/inputs/*.yaml"]
