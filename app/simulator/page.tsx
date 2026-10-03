import { notFound } from "next/navigation";
import { SimulatorClient } from "../../components/simulator/SimulatorClient";

export default function SimulatorPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <SimulatorClient />;
}
