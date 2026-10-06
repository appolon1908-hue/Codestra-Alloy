// alloy-entrypoint supervises Alloy and exposes only the private, read-only
// health and metrics surface required by the Codestra runtime contract.
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
	"time"
)

const (
	boundaryAddress = ":12345"
	nativeAddress   = "http://127.0.0.1:12346"
	maxResponseSize = 16 << 20
)

var allowedPaths = map[string]struct{}{
	"/-/healthy": {},
	"/-/ready":   {},
	"/metrics":   {},
}

type boundaryHandler struct {
	target *url.URL
	client *http.Client
}

func newBoundaryHandler(target string) (http.Handler, error) {
	parsed, err := url.Parse(target)
	if err != nil {
		return nil, fmt.Errorf("parse native address: %w", err)
	}
	if parsed.Scheme != "http" || parsed.Hostname() != "127.0.0.1" || parsed.Port() == "" || parsed.User != nil || parsed.Path != "" || parsed.RawQuery != "" {
		return nil, errors.New("native address must be an explicit loopback HTTP endpoint")
	}
	return &boundaryHandler{
		target: parsed,
		client: &http.Client{
			CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
				return http.ErrUseLastResponse
			},
			Timeout: 5 * time.Second,
			Transport: &http.Transport{
				DialContext:           (&net.Dialer{Timeout: 2 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
				DisableCompression:    true,
				MaxIdleConns:          4,
				MaxIdleConnsPerHost:   4,
				IdleConnTimeout:       30 * time.Second,
				ResponseHeaderTimeout: 3 * time.Second,
			},
		},
	}, nil
}

func (h *boundaryHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")

	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if r.URL.RawQuery != "" {
		http.NotFound(w, r)
		return
	}
	if _, ok := allowedPaths[r.URL.Path]; !ok {
		http.NotFound(w, r)
		return
	}

	target := *h.target
	target.Path = r.URL.Path
	request, err := http.NewRequestWithContext(r.Context(), r.Method, target.String(), nil)
	if err != nil {
		http.Error(w, "native endpoint unavailable", http.StatusBadGateway)
		return
	}
	response, err := h.client.Do(request)
	if err != nil {
		http.Error(w, "native endpoint unavailable", http.StatusBadGateway)
		return
	}
	defer response.Body.Close()

	body, err := io.ReadAll(io.LimitReader(response.Body, maxResponseSize+1))
	if err != nil || len(body) > maxResponseSize {
		http.Error(w, "native response rejected", http.StatusBadGateway)
		return
	}
	if contentType := response.Header.Get("Content-Type"); contentType != "" {
		w.Header().Set("Content-Type", contentType)
	}
	w.WriteHeader(response.StatusCode)
	if r.Method != http.MethodHead {
		_, _ = w.Write(body)
	}
}

func processExitCode(err error) int {
	if err == nil {
		return 0
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		if status, ok := exitErr.Sys().(syscall.WaitStatus); ok && status.Signaled() {
			return 128 + int(status.Signal())
		}
		return exitErr.ExitCode()
	}
	return 1
}

func run() int {
	handler, err := newBoundaryHandler(nativeAddress)
	if err != nil {
		fmt.Fprintln(os.Stderr, "alloy boundary configuration rejected")
		return 1
	}
	server := &http.Server{
		Addr:              boundaryAddress,
		Handler:           handler,
		ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout:       5 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       30 * time.Second,
		MaxHeaderBytes:    16 << 10,
	}

	child := exec.Command("/bin/alloy", os.Args[1:]...)
	child.Stdin = os.Stdin
	child.Stdout = os.Stdout
	child.Stderr = os.Stderr
	if err := child.Start(); err != nil {
		fmt.Fprintln(os.Stderr, "failed to start Alloy")
		return 1
	}

	childDone := make(chan error, 1)
	go func() { childDone <- child.Wait() }()
	serverDone := make(chan error, 1)
	go func() { serverDone <- server.ListenAndServe() }()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	defer signal.Stop(signals)

	shutdown := func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(ctx)
	}

	select {
	case err := <-childDone:
		shutdown()
		return processExitCode(err)
	case err := <-serverDone:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			fmt.Fprintln(os.Stderr, "Alloy HTTP boundary stopped unexpectedly")
		}
		_ = child.Process.Signal(syscall.SIGTERM)
		select {
		case childErr := <-childDone:
			return processExitCode(childErr)
		case <-time.After(10 * time.Second):
			_ = child.Process.Kill()
			<-childDone
			return 1
		}
	case received := <-signals:
		shutdown()
		_ = child.Process.Signal(received)
		select {
		case err := <-childDone:
			return processExitCode(err)
		case <-time.After(80 * time.Second):
			_ = child.Process.Kill()
			<-childDone
			return 1
		}
	}
}

func main() {
	os.Exit(run())
}
