package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestBoundaryAllowsOnlyReadOnlyHealthAndMetrics(t *testing.T) {
	receivedAuthorization := ""
	receivedCookie := ""
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedAuthorization = r.Header.Get("Authorization")
		receivedCookie = r.Header.Get("Cookie")
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		w.Header().Set("Set-Cookie", "native=secret")
		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte("alloy_build_info 1\n"))
	}))
	defer upstream.Close()

	handler, err := newBoundaryHandler(upstream.URL)
	if err != nil {
		t.Fatal(err)
	}
	boundary := httptest.NewServer(handler)
	defer boundary.Close()

	for _, path := range []string{"/-/healthy", "/-/ready", "/metrics"} {
		req, err := http.NewRequest(http.MethodGet, boundary.URL+path, nil)
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Authorization", "Bearer do-not-forward")
		req.Header.Set("Cookie", "session=do-not-forward")
		response, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		response.Body.Close()
		if response.StatusCode != http.StatusAccepted {
			t.Fatalf("%s returned %d", path, response.StatusCode)
		}
		if response.Header.Get("Set-Cookie") != "" {
			t.Fatalf("%s exposed an upstream cookie", path)
		}
	}
	if receivedAuthorization != "" || receivedCookie != "" {
		t.Fatal("the boundary forwarded caller credentials")
	}
}

func TestBoundaryDeniesAdministrativeAndUnexpectedRequests(t *testing.T) {
	upstreamCalls := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		upstreamCalls++
		w.WriteHeader(http.StatusOK)
	}))
	defer upstream.Close()

	handler, err := newBoundaryHandler(upstream.URL)
	if err != nil {
		t.Fatal(err)
	}
	tests := []struct {
		method string
		path   string
		status int
	}{
		{http.MethodGet, "/-/reload", http.StatusNotFound},
		{http.MethodPost, "/-/reload", http.StatusMethodNotAllowed},
		{http.MethodGet, "/-/support", http.StatusNotFound},
		{http.MethodGet, "/debug/pprof/", http.StatusNotFound},
		{http.MethodGet, "/api/v0/web/components", http.StatusNotFound},
		{http.MethodGet, "/metrics?caller=selected", http.StatusNotFound},
		{http.MethodDelete, "/metrics", http.StatusMethodNotAllowed},
	}
	for _, test := range tests {
		recorder := httptest.NewRecorder()
		request := httptest.NewRequest(test.method, test.path, strings.NewReader("ignored"))
		handler.ServeHTTP(recorder, request)
		if recorder.Code != test.status {
			t.Errorf("%s %s returned %d, want %d", test.method, test.path, recorder.Code, test.status)
		}
	}
	if upstreamCalls != 0 {
		t.Fatalf("denied requests reached native Alloy %d times", upstreamCalls)
	}
}

func TestBoundaryRejectsNonLoopbackUpstream(t *testing.T) {
	if _, err := newBoundaryHandler("https://alloy.example.test:12346"); err == nil {
		t.Fatal("non-loopback native address was accepted")
	}
	if _, err := newBoundaryHandler("http://127.0.0.1:12346/unexpected"); err == nil {
		t.Fatal("native address with a caller-selected path was accepted")
	}
}

func TestBoundaryDoesNotFollowNativeRedirect(t *testing.T) {
	destinationCalls := 0
	destination := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		destinationCalls++
		w.WriteHeader(http.StatusOK)
	}))
	defer destination.Close()
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Location", destination.URL)
		w.WriteHeader(http.StatusFound)
	}))
	defer upstream.Close()

	handler, err := newBoundaryHandler(upstream.URL)
	if err != nil {
		t.Fatal(err)
	}
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if recorder.Code != http.StatusFound {
		t.Fatalf("redirect returned %d", recorder.Code)
	}
	if destinationCalls != 0 {
		t.Fatal("the boundary followed a native redirect")
	}
	if recorder.Header().Get("Location") != "" {
		t.Fatal("the boundary exposed a native redirect target")
	}
}
