import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/environment.dart';
import 'app/makolo_app.dart';
import 'background/workmanager_runtime.dart';
import 'runtime/makolo_runtime_bootstrap.dart';
import 'runtime/runtime_ingress.dart';
import 'runtime/runtime_providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = MakoloRuntimeConfig.fromEnvironment();
  final runtime = MakoloRuntimeBootstrap();
  final ingress = RuntimeIngress();
  await runtime.initialize(config, ingress: ingress);
  try {
    await WorkmanagerRuntime().initialize(makoloBackgroundDispatcher);
  } catch (error, stackTrace) {
    await runtime.observability.reporter.report(
      error,
      stackTrace,
      tags: const {'service': 'workmanager', 'phase': 'initialize'},
    );
  }
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  runApp(
    ProviderScope(
      overrides: [runtimeIngressProvider.overrideWithValue(ingress)],
      child: const MakoloApp(),
    ),
  );
}
