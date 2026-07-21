import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { Corridor, ThemeName, ViewMode } from "./types";

interface SceneProps {
  corridors: Corridor[];
  theme: ThemeName;
  mode: ViewMode;
  replayProgress: number;
  spatial: boolean;
  locale: "en" | "zh";
}

const stateColor = (state: Corridor["state"], theme: ThemeName): string => {
  const colors = theme === "operations"
    ? { settled: "#78a989", moving: "#b5a274", queued: "#c28c4c", blocked: "#b76060" }
    : { settled: "#496f57", moving: "#786d55", queued: "#9b642c", blocked: "#8f373d" };
  return colors[state];
};

function RouteLine({ corridor, theme }: { corridor: Corridor; theme: ThemeName }) {
  const geometry = useMemo(() => {
    const mid = new THREE.Vector3(
      (corridor.start[0] + corridor.end[0]) / 2,
      Math.max(corridor.start[1], corridor.end[1]) + 1.05,
      (corridor.start[2] + corridor.end[2]) / 2,
    );
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...corridor.start),
      mid,
      new THREE.Vector3(...corridor.end),
    );
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(32));
  }, [corridor]);

  const line = useMemo(
    () =>
      new THREE.Line(
        geometry,
        new THREE.LineBasicMaterial({
          color: stateColor(corridor.state, theme),
          transparent: true,
          opacity: 0.78,
        }),
      ),
    [corridor.state, geometry, theme],
  );

  useEffect(() => {
    return () => {
      line.geometry.dispose();
      line.material.dispose();
    };
  }, [line]);

  return <primitive object={line} />;
}

function Pulse({ corridor, progress, theme, index }: { corridor: Corridor; progress: number; theme: ThemeName; index: number }) {
  const ref = useRef<THREE.Mesh | null>(null);
  const curve = useMemo(() => {
    const mid = new THREE.Vector3(
      (corridor.start[0] + corridor.end[0]) / 2,
      Math.max(corridor.start[1], corridor.end[1]) + 1.05,
      (corridor.start[2] + corridor.end[2]) / 2,
    );
    return new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...corridor.start),
      mid,
      new THREE.Vector3(...corridor.end),
    );
  }, [corridor]);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const live = (clock.getElapsedTime() * 0.095 + index * 0.17 + progress) % 1;
    ref.current.position.copy(curve.getPoint(live));
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.07, 14, 14]} />
      <meshStandardMaterial color={stateColor(corridor.state, theme)} roughness={0.55} metalness={0.12} />
    </mesh>
  );
}

function InstitutionNode({ position, label, critical, theme }: { position: [number, number, number]; label: string; critical?: boolean; theme: ThemeName }) {
  const body = critical ? "#8f373d" : theme === "operations" ? "#d2cbbb" : "#3f454b";
  const cap = theme === "operations" ? "#262b30" : "#ece8df";
  return (
    <group position={position}>
      <mesh position={[0, 0.16, 0]}>
        <cylinderGeometry args={[0.17, 0.2, 0.32, 20]} />
        <meshStandardMaterial color={body} roughness={0.72} />
      </mesh>
      <mesh position={[0, 0.36, 0]}>
        <boxGeometry args={[0.34, 0.06, 0.34]} />
        <meshStandardMaterial color={cap} roughness={0.75} />
      </mesh>
      <sprite position={[0, 0.72, 0]} scale={[1.35, 0.28, 1]}>
        <spriteMaterial color={theme === "operations" ? "#d8d2c7" : "#2f3337"} transparent opacity={0.9} />
      </sprite>
      <mesh position={[0, -0.06, 0]}>
        <ringGeometry args={[0.23, 0.27, 28]} />
        <meshBasicMaterial color={body} transparent opacity={0.45} side={THREE.DoubleSide} />
      </mesh>
      <mesh visible={false} name={label} />
    </group>
  );
}

function SpatialNetwork({ corridors, theme, mode, replayProgress }: Omit<SceneProps, "spatial" | "locale">) {
  const group = useRef<THREE.Group | null>(null);
  useFrame(({ clock }) => {
    if (!group.current) return;
    const target = mode === "infrastructure" ? -0.12 : mode === "hybrid" ? -0.07 : -0.02;
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, target, 0.04);
    group.current.rotation.z = Math.sin(clock.getElapsedTime() * 0.08) * 0.008;
  });

  const nodes = useMemo(() => {
    const positions = new Map<string, [number, number, number]>();
    corridors.forEach((corridor) => {
      positions.set(corridor.from, corridor.start);
      positions.set(corridor.to, corridor.end);
    });
    return [...positions.entries()];
  }, [corridors]);

  return (
    <group ref={group}>
      <gridHelper args={[12, 24, theme === "operations" ? "#3d4348" : "#a4a09a", theme === "operations" ? "#292e33" : "#d5d0c7"]} position={[0, -0.09, 0]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.1, 0]}>
        <planeGeometry args={[12, 7]} />
        <meshStandardMaterial color={theme === "operations" ? "#161a1e" : "#e9e5dc"} roughness={0.96} />
      </mesh>
      {corridors.map((corridor, index) => (
        <group key={corridor.id}>
          <RouteLine corridor={corridor} theme={theme} />
          {corridor.state !== "blocked" && <Pulse corridor={corridor} progress={replayProgress} theme={theme} index={index} />}
        </group>
      ))}
      {nodes.map(([label, position]) => (
        <InstitutionNode key={label} label={label} position={position} critical={label === "London"} theme={theme} />
      ))}
    </group>
  );
}

function GeographicFallback({ corridors, locale, theme }: Pick<SceneProps, "corridors" | "locale" | "theme">) {
  const mapPoint = (position: [number, number, number]): [number, number] => [
    360 + position[0] * 72,
    190 - position[1] * 62,
  ];
  return (
    <svg className="network-fallback" viewBox="0 0 720 380" role="img" aria-label="Geographically placed cross-border payment corridor schematic">
      <g className="geo-grid">
        {[80, 160, 240, 320].map((y) => <line key={`h-${y}`} x1="24" y1={y} x2="696" y2={y} />)}
        {[120, 240, 360, 480, 600].map((x) => <line key={`v-${x}`} x1={x} y1="24" x2={x} y2="356" />)}
      </g>
      <text x="28" y="42" className="map-caption">{locale === "zh" ? "按真实经纬关系布置的运行示意；不表示国界" : "Operational geography using real relative placement; boundaries are not represented"}</text>
      {corridors.map((corridor) => {
        const [x1, y1] = mapPoint(corridor.start);
        const [x2, y2] = mapPoint(corridor.end);
        const color = stateColor(corridor.state, theme);
        return (
          <g key={corridor.id}>
            <path d={`M ${x1} ${y1} Q ${(x1 + x2) / 2} ${Math.min(y1, y2) - 55} ${x2} ${y2}`} fill="none" stroke={color} strokeWidth="2" strokeDasharray={corridor.state === "queued" ? "7 5" : undefined} />
            <circle cx={x1} cy={y1} r="5" fill={color} />
            <circle cx={x2} cy={y2} r="5" fill={color} />
            <text x={x1 + 8} y={y1 - 8}>{corridor.from}</text>
            <text x={x2 + 8} y={y2 - 8}>{corridor.to}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function NetworkScene(props: SceneProps) {
  if (!props.spatial) return <GeographicFallback corridors={props.corridors} locale={props.locale} theme={props.theme} />;
  return (
    <div className="network-canvas" aria-label="3D cross-border settlement infrastructure scene">
      <Canvas camera={{ position: [0, 4.7, 9.7], fov: 42 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: false }}>
        <color attach="background" args={[props.theme === "operations" ? "#111519" : "#e9e5dc"]} />
        <ambientLight intensity={1.35} />
        <directionalLight position={[4, 8, 5]} intensity={2.1} color={props.theme === "operations" ? "#f0e8d8" : "#fffaf0"} />
        <SpatialNetwork corridors={props.corridors} theme={props.theme} mode={props.mode} replayProgress={props.replayProgress} />
      </Canvas>
    </div>
  );
}
