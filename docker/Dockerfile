FROM alpine

RUN apk update \
 && apk upgrade \
 && apk add graphviz ttf-freefont py3-jinja2 py3-lxml py-pip \
 && pip3 install pyyaml

COPY run_itassets.py ./itassets /itassets/
CMD ["python3", "/itassets/run_itassets.py", "/inputs/*.yaml"]
