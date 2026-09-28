const services = [
  { name: "Agente", url: process.env.NEXT_PUBLIC_AGENT_URL },
  { name: "API bancaria", url: process.env.NEXT_PUBLIC_BANK_API_URL },
  { name: "Langfuse", url: process.env.NEXT_PUBLIC_LANGFUSE_URL },
];

// Placeholder hasta el D1: aquí van el login con OTP, /chat y /console
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">Sofía</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Recepción de disputas de transacciones · Español y Portugués
      </p>
      <ul className="space-y-1 font-mono text-sm">
        {services.map(({ name, url }) => (
          <li key={name}>
            {name}: {url ?? "sin configurar"}
          </li>
        ))}
      </ul>
    </main>
  );
}
