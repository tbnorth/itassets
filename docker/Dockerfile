FROM alpine

RUN apk update \
 && apk upgrade \
 && apk add git openssh-client graphviz ttf-freefont py3-jinja2 py3-lxml py-pip \
 && pip3 install pyyaml

RUN mkdir -p ~/.ssh \
 && echo >> ~/.ssh/config 'Host *' \
 && echo >> ~/.ssh/config '    StrictHostKeyChecking no'

COPY run_itassets.py monitor.py ./itassets /itassets/
CMD ["python3", "/itassets/run_itassets.py", "/inputs/*.yaml"]
