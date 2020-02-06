#!/usr/bin/env python3

import yaml
import json
import csv

import subprocess

import argparse
import multiprocessing

import sys
import os
import glob

from plot import run_dash_server

YOUR_BEARER_TOKEN = "BEARER_TOKEN_PLACEHOLDER"
cpuCount = multiprocessing.cpu_count()
fileLoc = os.path.dirname(os.path.abspath(__file__))

def eprint(msg, indent):
    print((' ' * 2 * indent) + msg, file=sys.stderr)

def runBenchmarker(url, queries_file, query, query_variables, headers, rps, open_connections, duration, timeout):
    with open("/graphql-bench/ws/{}".format(queries_file), "r") as query_body_file:
        jsonPath = "/graphql-bench/ws/{}.json".format(queries_file)
        if not os.path.exists(jsonPath):
            with open(jsonPath, "w+") as query_body_json_file:
                if query_variables is not None:
                    json.dump({"query": query_body_file.read(),
                            "operationName": query,
                            "variables": query_variables }, query_body_json_file)
                else:
                    json.dump({"query": query_body_file.read(),
                            "operationName": query}, query_body_json_file)

    allHeaders = []

    # Omit the Auth header for Introspection.
    if query != "Introspection":
        allHeaders = ['-header',
                    'Authorization: Bearer {}'.format(YOUR_BEARER_TOKEN)]

    if headers != None:
        for header in headers:
            allHeaders.extend(['-header', header])

    # Run the benchmark
    # See https://github.com/tsenart/vegeta for documentation on these args.
    with open("/graphql-bench/ws/results.gob", "w+") as result_gob:
        subprocess.run(
            ['vegeta',
                'attack',
                '-rate', "{}".format(rps),
                '-duration', "{}s".format(duration),
                '-connections', "{}".format(open_connections),
                '-timeout', "{}".format(timeout),
                '-body', '/graphql-bench/ws/{}.json'.format(queries_file)]
            + allHeaders,
            input='POST {}'.format(url).encode('utf-8'),
            stdout=result_gob,
            stderr=subprocess.PIPE
        )

        result_gob.seek(0)

        # Output a vegeta report in a JSON format
        p_json_report = subprocess.run(
            ["vegeta",
                "report",
                "-type=json"],
            stdin=result_gob,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        result_gob.seek(0)

        # Create a report to be printed during the benchmark
        p_report = subprocess.run(
            ["vegeta",
                "report"],
            stdin=result_gob,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    # Remove generated files
    os.remove("/graphql-bench/ws/results.gob")

    if p_report.returncode != 0:
        for l in str(p_report.stderr, encoding="utf-8").splitlines():
            eprint(l, 3)
        return None
    else:
        for l in str(p_report.stdout, encoding="utf-8").splitlines():
            eprint(l, 3)
        return json.loads(str(p_json_report.stdout, encoding="utf-8"))


def bench_candidate(url, queries_file, query, query_variables, headers, rpsList, open_connections, duration, timeout):
    results = {}
    for rps in rpsList:
        eprint("+" * 20, 3)
        eprint("Rate: {rps} req/s || Duration: {duration}s || # Open connections: {open_connections} || Query variables: {query_variables}".format(
            rps=rps,
            duration=duration,
            open_connections=open_connections,
            query_variables=query_variables
        ), 3)
        res = runBenchmarker(url, queries_file, query, query_variables, headers,
                             rps, open_connections, duration, timeout)
        results[rps] = res
    return results

def bench_query(bench_params, desired_candidate):
    bench_name = bench_params["name"]

    eprint("=" * 20, 0)
    eprint("benchmark: {}".format(bench_name), 0)

    rpsList = bench_params["rps"]
    timeout = bench_params.get("timeout", "1s")
    duration = bench_params["duration"]
    open_connections = bench_params.get("open_connections", 20)
    warmup_duration = bench_params.get("warmup_duration", None)
    query = bench_params.get("query")
    queries_file = bench_params.get("queries_file")
    query_variables = bench_params.get("query_variables")
    headers = bench_params.get("headers")

    results = {}

    candidates = bench_params["candidates"]

    if desired_candidate:
        candidates = list(filter(lambda bc: bc['name'] == desired_candidate, candidates))
    
    for candidate in candidates:
        candidate_name = candidate["name"]
        candidate_url = candidate["url"]
        candidate_query = candidate.get("query", query)
        candidate_queries_file = candidate.get("queries_file", queries_file)
        candidate_query_variables = candidate.get("query_variables", query_variables)
        candidate_headers = candidate.get("headers", headers)

        eprint("-" * 20, 1)
        eprint("candidate: {} on {} at {}".format(
            candidate_query, candidate_name, candidate_url), 1)

        if warmup_duration:
            eprint("Warmup:", 2)
            bench_candidate(candidate_url, candidate_queries_file, candidate_query, candidate_query_variables, candidate_headers, rpsList, open_connections, warmup_duration, timeout)

        eprint("Benchmark:", 2)
        candidateRes = bench_candidate(candidate_url, candidate_queries_file, candidate_query, candidate_query_variables, candidate_headers, rpsList, open_connections, duration, timeout)
        results[candidate_name] = candidateRes

    eprint("=" * 20, 0)

    return {
        "benchmark": bench_name,
        "results": results
    }

def bench(args):
    bench_specs = yaml.load(args.spec, Loader=yaml.FullLoader)
    bench = args.bench
    desired_candidate = args.candidate
    if bench:
        bench_specs = list(filter(lambda bs: bs['name'] == bench, bench_specs))
        if not bench_specs:
            print("no such benchmark exists in the spec: {}".format(bench))
            sys.exit(1)
    results = []
    for bench_spec in bench_specs:
        results.append(bench_query(bench_spec, desired_candidate))
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--spec', nargs='?', type=argparse.FileType('r'),
        default=sys.stdin)
    parser.add_argument('--bench', nargs='?', type=str)
    parser.add_argument('--candidate', nargs='?', type=str)
    parser.add_argument('--token', nargs='?', type=str)
    args = parser.parse_args()

    if args.token is not None:
        YOUR_BEARER_TOKEN = args.token

    results = bench(args)
    with open("/graphql-bench/ws/bench_results.json", "w+") as resultFile:
        json.dump(results, resultFile)
