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

# install java
RUN mkdir -p /usr/share/man/man1
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -yq --no-install-recommends default-jdk && \
    apt-get clean

# procps for the top command
RUN apt-get -y update && apt-get -y install procps

# Copy MetricsCollector jar
RUN mkdir -p /usr/src/app/metricscollector
COPY metricscollector/ /usr/src/app/metricscollector/
RUN chmod +x /usr/src/app/metricscollector/

ENTRYPOINT ["python3", "-u", "/graphql-bench/bench.py"]
