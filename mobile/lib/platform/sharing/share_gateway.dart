import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

abstract interface class ShareGateway {
  Future<void> shareText(String text);
  Future<void> shareFiles({required List<String> paths, String? text});
  Future<bool> openExternal(Uri uri);
}

class SystemShareGateway implements ShareGateway {
  const SystemShareGateway();

  @override
  Future<void> shareText(String text) async {
    await SharePlus.instance.share(ShareParams(text: text));
  }

  @override
  Future<void> shareFiles({required List<String> paths, String? text}) async {
    await SharePlus.instance.share(
      ShareParams(text: text, files: paths.map(XFile.new).toList()),
    );
  }

  @override
  Future<bool> openExternal(Uri uri) {
    return launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}
