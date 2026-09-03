package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestReadOnlyProxyAllowsOnlyReadbackRoutes(t *testing.T) {
	var requests atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		requests.Add(1)
		writer.Header().Set("Content-Type", "text/plain")
		writer.WriteHeader(http.StatusOK)
		_, _ = writer.Write([]byte("safe readback"))
	}))
	defer upstream.Close()

	handler := newReadOnlyProxy(upstream.URL)
	for _, path := range []string{"/-/healthy", "/-/ready", "/metrics"} {
		request := httptest.NewRequest(http.MethodGet, path, nil)
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, request)
		if response.Code != http.StatusOK || response.Body.String() != "safe readback" {
			t.Fatalf("safe route %s was not proxied: status=%d body=%q", path, response.Code, response.Body.String())
		}
	}
	if requests.Load() != 3 {
		t.Fatalf("expected three upstream requests, got %d", requests.Load())
	}
}

func TestReadOnlyProxyDeniesAdministrationAndMutation(t *testing.T) {
	var requests atomic.Int32
	upstream := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		requests.Add(1)
		writer.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	handler := newReadOnlyProxy(upstream.URL)
	tests := []struct {
		method string
		path   string
	}{
		{method: http.MethodGet, path: "/-/reload"},
		{method: http.MethodPost, path: "/-/reload"},
		{method: http.MethodGet, path: "/-/support"},
		{method: http.MethodPost, path: "/metrics"},
		{method: http.MethodGet, path: "/metrics?debug=true"},
		{method: http.MethodGet, path: "/unknown"},
	}
	for _, test := range tests {
		request := httptest.NewRequest(test.method, test.path, strings.NewReader("ignored"))
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, request)
		if response.Code != http.StatusForbidden {
			t.Fatalf("%s %s returned %d", test.method, test.path, response.Code)
		}
	}
	if requests.Load() != 0 {
		t.Fatalf("denied requests reached native Alloy: %d", requests.Load())
	}
}

func TestReadOnlyProxyBoundsUpstreamResponse(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		_, _ = writer.Write([]byte(strings.Repeat("x", maxResponseBytes+1)))
	}))
	defer upstream.Close()

	request := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	response := httptest.NewRecorder()
	newReadOnlyProxy(upstream.URL).ServeHTTP(response, request)
	if response.Code != http.StatusBadGateway {
		t.Fatalf("oversized response returned %d", response.Code)
	}
}
