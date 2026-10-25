import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Geographic schematic from recorded data, not satellite imagery or clearance.
class SurveyGeometryPainter extends CustomPainter {
  SurveyGeometryPainter(this.detail);
  final Map<String, dynamic> detail;

  @override
  void paint(Canvas canvas, Size size) {
    final mission = detail['mission'] as Map<String, dynamic>;
    final ring = mission['boundary']['coordinates'][0] as List<dynamic>;
    final observations = detail['observations'] as List<dynamic>;
    final all = [...ring, ...observations.map((o) => [o['longitude'], o['latitude']])];
    if (all.isEmpty) return;
    final minX = all.map((p) => (p[0] as num).toDouble()).reduce(math.min);
    final maxX = all.map((p) => (p[0] as num).toDouble()).reduce(math.max);
    final minY = all.map((p) => (p[1] as num).toDouble()).reduce(math.min);
    final maxY = all.map((p) => (p[1] as num).toDouble()).reduce(math.max);
    final longitudeScale = math.cos(minY * math.pi / 180);
    final scale = math.min((size.width - 32) / math.max((maxX-minX)*longitudeScale, .00001), (size.height-32) / math.max(maxY-minY, .00001));
    Offset project(dynamic p) => Offset(16 + ((p[0] as num).toDouble()-minX)*longitudeScale*scale, size.height-16-((p[1] as num).toDouble()-minY)*scale);
    void draw(List<dynamic> points, Color color, {bool fill = false}) {
      if (points.isEmpty) return;
      final path = Path()..moveTo(project(points.first).dx, project(points.first).dy);
      for (final p in points.skip(1)) { final v=project(p); path.lineTo(v.dx,v.dy); }
      if (fill) path.close();
      final paint = Paint()..color=color..strokeWidth=2;
      paint.style = fill ? PaintingStyle.fill : PaintingStyle.stroke;
      canvas.drawPath(path, paint);
    }
    draw(ring, Colors.blue.withAlpha(35), fill:true);
    draw(ring, Colors.blueAccent);
    draw(mission['waypoints'] as List<dynamic>, const Color(0xFFE1CC8E));
    draw(observations.map((o) => [o['longitude'],o['latitude']]).toList(), const Color(0xFF71DBBF));
    for (final target in detail['detections'] as List<dynamic>) {
      canvas.drawCircle(project([target['longitude'],target['latitude']]),4,Paint()..color=Colors.redAccent);
    }
    if(observations.isNotEmpty) {
      final last=observations.last;
      final center=project([last['longitude'],last['latitude']]);
      final outline=Paint()..color=Colors.lightBlueAccent..style=PaintingStyle.stroke..strokeWidth=2;
      canvas.drawLine(center+const Offset(-8,-8),center+const Offset(8,8),outline);
      canvas.drawLine(center+const Offset(8,-8),center+const Offset(-8,8),outline);
      for(final offset in [const Offset(-8,-8),const Offset(8,-8),const Offset(-8,8),const Offset(8,8)]) {
        canvas.drawCircle(center+offset,5,outline);
      }
      canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center:center,width:7,height:10),const Radius.circular(2)),Paint()..color=Colors.lightBlueAccent);
    }
  }

  @override
  bool shouldRepaint(covariant SurveyGeometryPainter oldDelegate) => oldDelegate.detail != detail;
}
