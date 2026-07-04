SVC      := mercury
HARBOR   ?= harbor.georgievski.net/live
REGISTRY ?= live
VERSION  := $(shell cat VERSION 2>/dev/null || echo "0.0.0")

DOCKER_BUILD_FLAGS ?=
ifdef NC
DOCKER_BUILD_FLAGS += --no-cache
endif

.PHONY: image tag push release version

version:
	@echo $(VERSION)

image:
	docker build $(DOCKER_BUILD_FLAGS) --build-arg VERSION=$(VERSION) -t $(REGISTRY)/$(SVC):$(VERSION) .
	@echo "Built $(REGISTRY)/$(SVC):$(VERSION)"

tag:
	docker tag $(REGISTRY)/$(SVC):$(VERSION) $(HARBOR)/$(SVC):$(VERSION)
	@echo "Tagged $(HARBOR)/$(SVC):$(VERSION)"

push:
	docker push $(HARBOR)/$(SVC):$(VERSION)

release: image tag push
