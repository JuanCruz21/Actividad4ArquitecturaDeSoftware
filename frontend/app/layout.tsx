import type { Metadata } from "next";
import "./globals.css";
import { Navegacion } from "@/components/Navegacion";
import { ProveedorSesion } from "@/components/Sesion";

export const metadata: Metadata = {
  title: "LabCloud Distributed",
  description:
    "Panel de control del prototipo de arquitectura distribuida de LabCloud S.A.S.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased">
        <ProveedorSesion>
          {/* Columna en pantallas estrechas (cabecera arriba), fila en anchas. */}
          <div className="flex min-h-screen flex-col lg:flex-row">
            <Navegacion />
            <main className="min-w-0 flex-1">
              <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
                {children}
              </div>
            </main>
          </div>
        </ProveedorSesion>
      </body>
    </html>
  );
}
