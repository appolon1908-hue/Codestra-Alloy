package main

import (
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	proxyListenAddress = ":12346"
	nativeAlloyURL     = "http://127.0.0.1:12345"
	maxResponseBytes   = 16 << 20
)

var allowedReadPaths = map[string]struct{}{
	"/-/healthy": {},
	"/-/ready":   {},
	"/metrics":   {},
}

type readOnlyProxy struct {
	upstream string
	client   *http.Client
}

func newReadOnlyProxy(upstream string) http.Handler {
	transport := &http.Transport{
		Proxy:                 nil,
		DialContext:           (&net.Dialer{Timeout: 2 * time.Second}).DialContext,
		DisableCompression:    true,
		MaxIdleConns:          4,
		MaxIdleConnsPerHost:   4,
		ResponseHeaderTimeout: 5 * time.Second,
	}
	return &readOnlyProxy{
		upstream: strings.TrimRight(upstream, "/"),
		client: &http.Client{
			Transport: transport,
			Timeout:   10 * time.Second,
		},
	}
}

func (proxy *readOnlyProxy) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodGet || request.URL.RawQuery != "" {
		http.Error(writer, "forbidden", http.StatusForbidden)
		return
	}
	if _, allowed := allowedReadPaths[request.URL.Path]; !allowed {
		http.Error(writer, "forbidden", http.StatusForbidden)
		return
	}

	upstreamRequest, err := http.NewRequestWithContext(
		request.Context(),
		http.MethodGet,
		proxy.upstream+request.URL.Path,
		nil,
	)
	if err != nil {
		http.Error(writer, "upstream unavailable", http.StatusBadGateway)
		return
	}
	upstreamRequest.Header.Set("User-Agent", "codestra-alloy-readonly-proxy/1")
	if accept := request.Header.Get("Accept"); accept != "" {
		upstreamRequest.Header.Set("Accept", accept)
	}

	response, err := proxy.client.Do(upstreamRequest)
	if err != nil {
		http.Error(writer, "upstream unavailable", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()

	body, err := io.ReadAll(io.LimitReader(response.Body, maxResponseBytes+1))
	if err != nil || len(body) > maxResponseBytes {
		http.Error(writer, "upstream response rejected", http.StatusBadGateway)
		return
	}
	if contentType := response.Header.Get("Content-Type"); contentType != "" {
		writer.Header().Set("Content-Type", contentType)
	}
	writer.Header().Set("Cache-Control", "no-store")
	writer.Header().Set("X-Content-Type-Options", "nosniff")
	writer.WriteHeader(response.StatusCode)
	_, _ = writer.Write(body)
}

func main() {
	server := &http.Server{
		Addr:              proxyListenAddress,
		Handler:           newReadOnlyProxy(nativeAlloyURL),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       30 * time.Second,
		MaxHeaderBytes:    32 << 10,
		ErrorLog:          log.New(os.Stderr, "alloy-readonly-proxy: ", log.LstdFlags),
	}
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Printf("alloy-readonly-proxy stopped: %v", err)
		os.Exit(1)
	}
}
