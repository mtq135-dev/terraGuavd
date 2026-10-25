import 'dart:convert';
import 'dart:async';
import 'survey_geometry.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const navy = Color(0xFF081923);
const surface = Color(0xFF102A37);
const cream = Color(0xFFF2EDDF);
const accent = Color(0xFFEC3349);
const apiBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://127.0.0.1:8000');

void main() => runApp(const TerraGuavdField());

class TerraGuavdField extends StatelessWidget {
  const TerraGuavdField({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'TerraGuavd Field',
    theme: ThemeData(
      brightness: Brightness.dark, scaffoldBackgroundColor: navy,
      colorScheme: const ColorScheme.dark(primary: accent, surface: surface, onSurface: cream),
      appBarTheme: const AppBarTheme(backgroundColor: navy, foregroundColor: cream),
      inputDecorationTheme: const InputDecorationTheme(filled: true, fillColor: surface, border: OutlineInputBorder()),
      navigationBarTheme: NavigationBarThemeData(backgroundColor: navy, indicatorColor: accent.withAlpha(60)),
    ),
    home: const FieldWorkspace(),
  );
}

class FieldWorkspace extends StatefulWidget {
  const FieldWorkspace({super.key});
  @override
  State<FieldWorkspace> createState() => _FieldWorkspaceState();
}

class _FieldWorkspaceState extends State<FieldWorkspace> {
  final username = TextEditingController();
  final password = TextEditingController();
  final client = http.Client();
  String? token;
  String? error;
  String account = '';
  bool busy = false;
  int page = 0;
  Map<String, dynamic>? dashboard;
  Map<String, dynamic>? detail;
  String? selected;
  Timer? polling;
  static const pages = ['Home', 'Missions', 'Detections', 'Alerts', 'More'];

  @override
  void dispose() { polling?.cancel(); username.dispose(); password.dispose(); client.close(); super.dispose(); }

  Future<Map<String, dynamic>> request(String path, {Map<String, String>? body, String? session}) async {
    final headers = <String, String>{'Content-Type': 'application/json', if ((session ?? token) != null) 'Authorization': 'Bearer ${session ?? token}'};
    final uri = Uri.parse('$apiBase/api/v1$path');
    final response = await (body != null ? client.post(uri, headers: headers, body: jsonEncode(body)) : client.get(uri, headers: headers)).timeout(const Duration(seconds: 15));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(response.statusCode == 401 ? 'Invalid credentials or expired session.' : response.statusCode == 403 ? 'Access denied.' : 'Service unavailable.');
    }
    return response.body.isEmpty ? {} : jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> signIn() async {
    if (username.text.isEmpty || password.text.isEmpty) { setState(() => error = 'Enter username and password.'); return; }
    setState(() { busy = true; error = null; });
    String? newToken;
    try {
      final auth = await request('/auth/login', body: {'username': username.text, 'password': password.text});
      newToken = auth['access_token'] as String;
      final identity = await request('/auth/me', session: newToken);
      if (identity['role'] != 'field_personnel') { throw Exception('Use the web workspace for this role.'); }
      final data = await request('/dashboards/field_personnel', session: newToken);
      if (!mounted) return;
      setState(() { token = newToken; account = identity['username'] as String; dashboard = data; page = 0; });
      password.clear();
      polling?.cancel();
      polling = Timer.periodic(const Duration(seconds: 4), (_) { if (!busy && token != null) refresh(); });
      final missions = data['missions'] as List<dynamic>? ?? [];
      if (missions.isNotEmpty) await selectMission(missions.first['id'] as String);
    } catch (exception) {
      if (newToken != null) {
        try { await request('/auth/logout', body: {}, session: newToken); } catch (_) { /* Absolute server expiry remains enforced. */ }
      }
      if (mounted) setState(() => error = exception.toString());
    } finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> refresh() async {
    setState(() { busy = true; error = null; });
    try {
      final data = await request('/dashboards/field_personnel');
      if (mounted) setState(() => dashboard = data);
      if (selected != null) {
        final result = await request('/missions/$selected');
        if (mounted) setState(() => detail = result);
      }
    } catch (exception) { if (mounted) setState(() => error = exception.toString()); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> signOut() async {
    polling?.cancel();
    String? message;
    try { await request('/auth/logout', body: {}); }
    catch (_) { message = 'Local session cleared. Server session expires within 30 minutes.'; }
    if (mounted) setState(() { token = null; dashboard = null; detail = null; selected = null; error = message; });
  }

  Future<void> selectMission(String id) async {
    try { final result = await request('/missions/$id'); if (mounted) setState(() { selected = id; detail = result; }); }
    catch (exception) { if (mounted) setState(() => error = exception.toString()); }
  }

  Future<void> requestStop() async {
    if (selected == null) return;
    final reason = TextEditingController();
    final accepted = await showDialog<bool>(context: context, builder: (dialogContext) => AlertDialog(
      title: const Text('Request mission stop'), content: TextField(controller: reason, decoration: const InputDecoration(labelText: 'Reason (at least 3 characters)')),
      actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')), FilledButton(onPressed: () { if (reason.text.trim().length >= 3) Navigator.pop(dialogContext, true); }, child: const Text('Send request'))],
    ));
    final text = reason.text; reason.dispose();
    if (accepted != true) return;
    try { final response = await request('/missions/$selected/stop-request', body: {'reason': text}); if (mounted) setState(() => error = response['notice'] as String); }
    catch (exception) { if (mounted) setState(() => error = exception.toString()); }
  }

  int count(String key) => (dashboard?[key] as List<dynamic>?)?.length ?? 0;

  Widget empty(String text, {IconData icon = Icons.layers_outlined}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 24),
    child: Column(children: [Icon(icon, size: 32, color: Colors.blueGrey), const SizedBox(height: 12), Text(text, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFA6BBC6), height: 1.6))]),
  );

  List<Widget> content() {
    final missions = dashboard?['missions'] as List<dynamic>? ?? [];
    final targets = detail?['detections'] as List<dynamic>? ?? dashboard?['potential_detections'] as List<dynamic>? ?? [];
    final events = detail?['events'] as List<dynamic>? ?? dashboard?['alerts'] as List<dynamic>? ?? [];
    final surveys = dashboard?['survey_attempts'] as List<dynamic>? ?? [];
    final observations = detail?['observations'] as List<dynamic>? ?? [];
    final telemetry = observations.isEmpty ? null : observations.last as Map<String, dynamic>;
    final mission = detail?['mission'] as Map<String, dynamic>?;
    final active = ['STARTING_SIMULATION','WAITING_FOR_VEHICLE','UPLOADING','EXECUTING','PAUSED','CANCELLING'].contains(mission?['state']);
    switch (page) {
      case 1: return [FieldCard(title: 'Assigned missions · ${missions.length}', child: missions.isEmpty ? empty('No assigned missions.', icon: Icons.assignment_outlined) : Column(children: missions.map((m) => ListTile(selected: selected == m['id'], leading: const Icon(Icons.location_on_outlined), title: Text(m['name'] as String), subtitle: Text('${m['state']} · ${m['area_id']}'), onTap: () => selectMission(m['id'] as String))).toList())), FieldCard(title: 'Survey history', child: surveys.isEmpty ? empty('No finalized survey attempts.') : Column(children: surveys.map((s) => ListTile(title: Text('${s['status']} · ${s['coverage_percent']}% experimental coverage'), subtitle: Text('${s['finished_at']} · ${s['algorithm_version']}'))).toList()))];
      case 2: return [FieldCard(title: 'Potential detections · ${targets.length}', child: targets.isEmpty ? empty('No recorded potential targets.', icon: Icons.warning_amber) : Column(children: targets.map((t) => ListTile(leading: const Icon(Icons.warning_amber, color: accent), title: Text('Potential target · ${t['confidence']}'), subtitle: Text('Synthetic and unverified\n${t['latitude']}, ${t['longitude']}\n${t['processing_version']}'), onTap: () => showDialog<void>(context: context, builder: (ctx) => AlertDialog(title: const Text('Potential target details'), content: SelectableText(const JsonEncoder.withIndent('  ').convert(t)), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))])))).toList())), const FieldCard(title: 'Interpretation', child: Text('Confidence is not verification. Synthetic normalized-feature fixtures are not physical GPR or metal-detector measurements.'))];
      case 3: return [FieldCard(title: 'Mission events & alerts', child: events.isEmpty ? empty('No assigned alerts.', icon: Icons.notifications_none) : Column(children: events.map((e) => ListTile(title: Text(e['kind'] as String), subtitle: Text('${e['detail']}\n${e['created_at']}'))).toList())), FieldCard(title: 'Actions', child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [FilledButton(onPressed: active ? requestStop : null, child: const Text('Request mission stop')), const SizedBox(height: 10), const Text('Notifies the assigned operator. A request never directly commands the autopilot.')]))];
      case 4: return [FieldCard(title: 'Account & access', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(account), const SizedBox(height: 12), const Text('Field Personnel · assigned-mission monitoring only.'), const SizedBox(height: 12), OutlinedButton(onPressed: signOut, child: const Text('Sign out'))]))];
      default: return [FieldCard(title: mission?['name'] as String? ?? 'Current mission', trailing: Text(mission?['state'] as String? ?? 'Unassigned', style: const TextStyle(color: Colors.blueGrey)), child: mission == null ? empty('Select a mission from Missions.', icon: Icons.flight) : Text('Isolated PX4/Gazebo SITL\nExperimental coverage: ${detail?['coverage']['coverage_percent']}%\nSurveyed does not mean cleared or safe.')), FieldCard(title: 'Survey geometry · schematic', child: detail == null ? empty('No survey selected.', icon: Icons.map_outlined) : Column(children: [SizedBox(height: 260, child: InteractiveViewer(child: CustomPaint(size: const Size(500, 260), painter: SurveyGeometryPainter(detail!)))), const Text('Blue: planned area · cream: route · mint: actual SITL track · red: synthetic potential targets', style: TextStyle(fontSize: 11))])), FieldCard(title: 'Vehicle telemetry · SITL', child: Wrap(spacing: 28, runSpacing: 20, children: [TelemetryValue('Battery', '${telemetry?['battery_percent'] ?? '—'}%'), TelemetryValue('Altitude', '${telemetry?['altitude_m'] ?? '—'} m'), TelemetryValue('Speed', '${telemetry?['speed_m_s'] ?? '—'} m/s'), TelemetryValue('Samples', '${observations.length}')]))];
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(token == null ? 'TerraGuavd' : page == 0 ? 'TerraGuavd · Field' : pages[page]), actions: [if (token != null) IconButton(tooltip: 'Refresh workspace', onPressed: busy ? null : refresh, icon: const Icon(Icons.refresh))]),
    body: SafeArea(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 650), child: ListView(padding: const EdgeInsets.all(16), children: [
      Container(padding: const EdgeInsets.all(12), color: const Color(0xFF42242B), child: const Text('SIMULATION ONLY\nPotential detections are unverified. Surveyed does not mean cleared or safe.', style: TextStyle(fontSize: 12, height: 1.5, color: Color(0xFFF0C9B8)))),
      if (busy) const LinearProgressIndicator(),
      if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Semantics(liveRegion: true, child: Text(error!, style: const TextStyle(color: Colors.redAccent)))),
      const SizedBox(height: 16),
      if (token == null) FieldCard(title: 'Field Personnel sign in', child: Column(children: [TextField(controller: username, autofillHints: const [AutofillHints.username], decoration: const InputDecoration(labelText: 'Username')), const SizedBox(height: 16), TextField(controller: password, obscureText: true, autofillHints: const [AutofillHints.password], onSubmitted: (_) { if (!busy) signIn(); }, decoration: const InputDecoration(labelText: 'Password')), const SizedBox(height: 20), SizedBox(width: double.infinity, child: FilledButton(onPressed: busy ? null : signIn, child: const Text('Sign in')))])) else ...content(),
    ])))),
    bottomNavigationBar: token == null ? null : NavigationBar(selectedIndex: page, onDestinationSelected: (value) => setState(() => page = value), destinations: const [NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'), NavigationDestination(icon: Icon(Icons.location_on_outlined), label: 'Missions'), NavigationDestination(icon: Icon(Icons.warning_amber), label: 'Detections'), NavigationDestination(icon: Icon(Icons.notifications_none), label: 'Alerts'), NavigationDestination(icon: Icon(Icons.more_horiz), label: 'More')]),
  );
}

class FieldCard extends StatelessWidget {
  const FieldCard({required this.title, required this.child, this.trailing, super.key});
  final String title;
  final Widget child;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Container(margin: const EdgeInsets.only(bottom: 16), padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: surface, borderRadius: BorderRadius.circular(10), border: Border.all(color: const Color(0xFF25414F))), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [Row(children: [Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w600))), if (trailing != null) trailing!]), const SizedBox(height: 12), child]));
}

class TelemetryValue extends StatelessWidget {
  const TelemetryValue(this.label, this.value, {super.key});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: const TextStyle(fontSize: 11, color: Colors.blueGrey)), const SizedBox(height: 8), Text(value)]);
}
