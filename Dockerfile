FROM golang:1.13.5-stretch as go-image

RUN go get -u github.com/tsenart/vegeta


FROM python:3.7-slim
RUN apt-get update \
    && apt-get install -y libssl1.1 jq \
    && apt-get clean

COPY --from=go-image /go/bin/vegeta /usr/bin/vegeta

COPY requirements.txt /graphql-bench/requirements.txt
RUN pip install --no-cache-dir -r /graphql-bench/requirements.txt

COPY bench.py plot.py /graphql-bench/

RUN mkdir -p /graphql-bench/ws
WORKDIR /graphql-bench/ws/

ENTRYPOINT ["python3", "-u", "/graphql-bench/bench.py"]
