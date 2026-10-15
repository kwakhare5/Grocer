import { notFound } from "next/navigation";
import { SimulatorClient } from "../../components/simulator/SimulatorClient";

export default function SimulatorPage() {
  const isEnabled =
    process.env.NODE_ENV === "development" ||
    process.env.NEXT_PUBLIC_ENABLE_SIMULATOR !== "false";

  if (!isEnabled) notFound();
  return <SimulatorClient />;
}
