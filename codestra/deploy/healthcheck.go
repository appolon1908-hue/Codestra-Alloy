package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

const defaultURL = "http://127.0.0.1:12345/-/ready"

func main() {
	url := os.Getenv("ALLOY_HEALTHCHECK_URL")
	if url == "" {
		url = defaultURL
	}

	method := os.Getenv("ALLOY_HEALTHCHECK_METHOD")
	if method == "" {
		method = http.MethodGet
	}
	if method != http.MethodGet && method != http.MethodPost {
		fmt.Fprintln(os.Stderr, "alloy readiness method is not allowed")
		os.Exit(1)
	}

	expectedStatus := 0
	if raw := os.Getenv("ALLOY_HEALTHCHECK_EXPECT_STATUS"); raw != "" {
		value, parseErr := strconv.Atoi(raw)
		if parseErr != nil || value < 100 || value > 599 {
			fmt.Fprintln(os.Stderr, "alloy readiness expected status is invalid")
			os.Exit(1)
		}
		expectedStatus = value
	}

	request, err := http.NewRequest(method, url, nil) // #nosec G107 -- operator-controlled local readiness endpoint.
	if err != nil {
		fmt.Fprintln(os.Stderr, "alloy readiness request is invalid")
		os.Exit(1)
	}
	client := &http.Client{
		Transport: &http.Transport{Proxy: nil},
		Timeout:   5 * time.Second,
		CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
	resp, err := client.Do(request)
	if err != nil {
		fmt.Fprintf(os.Stderr, "alloy readiness request failed: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4096))

	if expectedStatus != 0 && resp.StatusCode != expectedStatus {
		fmt.Fprintf(os.Stderr, "alloy readiness returned HTTP %d\n", resp.StatusCode)
		os.Exit(1)
	}
	if expectedStatus == 0 && (resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices) {
		fmt.Fprintf(os.Stderr, "alloy readiness returned HTTP %d\n", resp.StatusCode)
		os.Exit(1)
	}
}
