# Multi-stage: compile with Go toolchain, run on minimal Alpine.
FROM golang:1.22-alpine AS build
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o app .

FROM alpine:3.19
WORKDIR /app
COPY --from=build /build/app .
EXPOSE 8080
ENTRYPOINT ["./app"]
