import { useEffect, useRef } from "react";
import * as THREE from "three";

const COLS = 12;
const ROWS = 3;
const COUNT = COLS * ROWS;

/** Latar 3D ringan: "batang candlestick" yang bergelombang pelan. Dimuat malas (lazy) hanya di halaman login. */
export default function Hero3D() {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
    camera.position.set(0, 4, 15);
    camera.lookAt(0, 1.2, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 1.4);
    sun.position.set(5, 10, 7);
    scene.add(sun);

    const geometry = new THREE.BoxGeometry(0.55, 1, 0.55);
    const material = new THREE.MeshStandardMaterial({ roughness: 0.35, metalness: 0.15 });
    const mesh = new THREE.InstancedMesh(geometry, material, COUNT);

    // Pseudo-acak berbenih agar tampilannya konsisten di setiap kunjungan.
    let seed = 7;
    const rnd = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
    const up = new THREE.Color(0x34d399);
    const down = new THREE.Color(0xf87171);
    const bars: { x: number; z: number; h: number; phase: number }[] = [];
    for (let i = 0; i < COUNT; i++) {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      bars.push({ x: (col - (COLS - 1) / 2) * 1.15, z: (row - 1) * 1.7, h: 0.8 + rnd() * 3.2, phase: rnd() * Math.PI * 2 });
      mesh.setColorAt(i, rnd() > 0.38 ? up : down);
    }
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;

    const group = new THREE.Group();
    group.add(mesh);
    scene.add(group);

    const dummy = new THREE.Object3D();
    const resize = () => {
      const w = el.clientWidth || 1;
      const h = el.clientHeight || 1;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const t0 = performance.now();
    let raf = 0;
    const tick = () => {
      const t = (performance.now() - t0) / 1000;
      for (let i = 0; i < COUNT; i++) {
        const b = bars[i];
        const h = b.h * (0.75 + 0.25 * Math.sin(t * 0.8 + b.phase));
        dummy.position.set(b.x, h / 2, b.z);
        dummy.scale.set(1, h, 1);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
      }
      mesh.instanceMatrix.needsUpdate = true;
      group.rotation.y = Math.sin(t * 0.15) * 0.35;
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    // Hemat baterai: berhenti saat tab tidak terlihat.
    const onVisibility = () => {
      if (document.hidden) {
        cancelAnimationFrame(raf);
        raf = 0;
      } else if (!raf) {
        raf = requestAnimationFrame(tick);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      ro.disconnect();
      mesh.dispose();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={boxRef} className="hero3d" aria-hidden="true" />;
}
