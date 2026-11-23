import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Native filesystem locations; feature code never imports path_provider.
abstract final class NativeDirectories {
  static Future<Directory> temporary() => getTemporaryDirectory();
  static Future<Directory> support() => getApplicationSupportDirectory();
}
