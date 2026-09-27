import '../../navigation/destination.dart';
import 'push_signal.dart';

class NormalizedPushSignal {
  const NormalizedPushSignal({
    required this.sourceKeys,
    this.destination,
  });

  final Set<String> sourceKeys;
  final StructuredDestination? destination;
}

typedef PushSignalNormalizer =
    Future<NormalizedPushSignal?> Function(PushSignal signal);
typedef PushSourceInvalidator = Future<void> Function(String sourceKey);
typedef PushOwnerRefresh = Future<void> Function(Set<String> sourceKeys);

class PushSignalProcessor {
  const PushSignalProcessor({
    required this.normalize,
    required this.invalidate,
    required this.refresh,
  });

  final PushSignalNormalizer normalize;
  final PushSourceInvalidator invalidate;
  final PushOwnerRefresh refresh;

  Future<NormalizedPushSignal?> process(PushSignal signal) async {
    final normalized = await normalize(signal);
    if (normalized == null) return null;

    for (final sourceKey in normalized.sourceKeys) {
      await invalidate(sourceKey);
    }
    await refresh(normalized.sourceKeys);
    return normalized;
  }
}
