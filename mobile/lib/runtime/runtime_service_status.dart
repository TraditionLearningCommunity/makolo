enum RuntimeServiceState { disabled, initializing, ready, failed }

class RuntimeServiceStatus {
  const RuntimeServiceStatus(this.state, {this.detail});

  const RuntimeServiceStatus.disabled() : this(RuntimeServiceState.disabled);
  const RuntimeServiceStatus.ready() : this(RuntimeServiceState.ready);
  const RuntimeServiceStatus.failed([String? detail])
    : this(RuntimeServiceState.failed, detail: detail);

  final RuntimeServiceState state;
  final String? detail;

  bool get isReady => state == RuntimeServiceState.ready;
}
