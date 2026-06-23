import { useEffect, useRef, useState } from "react";
import {
  getRun,
  submitCalibration,
  submitCostBenefit,
  submitForecast,
  submitLitPop,
  submitRun,
  submitSupplyChain,
  submitTransition,
  submitUncertainty,
} from "./api";
import type { MeasureSpec, Run, TransitionResult } from "../types";

const DEFAULT_MEASURE: MeasureSpec = {
  name: "Retrofit",
  cost: 1_000_000,
  damage_reduction: 0.3,
  risk_transf_attach: 0,
  risk_transf_cover: 0,
};

/**
 * Owns all run state + polling at the App level so results (and in-flight polling)
 * survive tab switches. Resets when the session changes.
 */
export function useResults(sessionId: string) {
  const [physRun, setPhysRun] = useState<Run | null>(null);
  const [transition, setTransition] = useState<TransitionResult | null>(null);
  const [physBusy, setPhysBusy] = useState(false);
  const [physErr, setPhysErr] = useState<string | null>(null);

  const [cbRun, setCbRun] = useState<Run | null>(null);
  const [cbMeasures, setCbMeasures] = useState<MeasureSpec[]>([{ ...DEFAULT_MEASURE }]);
  const [cbBusy, setCbBusy] = useState(false);
  const [cbErr, setCbErr] = useState<string | null>(null);

  const [uncRun, setUncRun] = useState<Run | null>(null);
  const [uncBusy, setUncBusy] = useState(false);
  const [uncErr, setUncErr] = useState<string | null>(null);

  const [litpopRun, setLitpopRun] = useState<Run | null>(null);
  const [litpopBusy, setLitpopBusy] = useState(false);
  const [litpopErr, setLitpopErr] = useState<string | null>(null);

  const [scRun, setScRun] = useState<Run | null>(null);
  const [scBusy, setScBusy] = useState(false);
  const [scErr, setScErr] = useState<string | null>(null);

  const [calRun, setCalRun] = useState<Run | null>(null);
  const [calBusy, setCalBusy] = useState(false);
  const [calErr, setCalErr] = useState<string | null>(null);

  const [fcRun, setFcRun] = useState<Run | null>(null);
  const [fcBusy, setFcBusy] = useState(false);
  const [fcErr, setFcErr] = useState<string | null>(null);

  // Reset everything when the session changes.
  const sid = useRef(sessionId);
  useEffect(() => {
    if (sid.current === sessionId) return;
    sid.current = sessionId;
    setPhysRun(null);
    setTransition(null);
    setPhysErr(null);
    setCbRun(null);
    setCbErr(null);
    setCbMeasures([{ ...DEFAULT_MEASURE }]);
    setUncRun(null);
    setUncErr(null);
    setLitpopRun(null);
    setLitpopErr(null);
    setScRun(null);
    setScErr(null);
    setCalRun(null);
    setCalErr(null);
    setFcRun(null);
    setFcErr(null);
  }, [sessionId]);

  // Poll the LitPop run while in flight.
  useEffect(() => {
    if (!litpopRun || (litpopRun.status !== "queued" && litpopRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setLitpopRun(await getRun(sessionId, litpopRun.id));
      } catch (e) {
        setLitpopErr(String(e));
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [litpopRun, sessionId]);

  // Poll the uncertainty run while in flight.
  useEffect(() => {
    if (!uncRun || (uncRun.status !== "queued" && uncRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setUncRun(await getRun(sessionId, uncRun.id));
      } catch (e) {
        setUncErr(String(e));
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [uncRun, sessionId]);

  // Poll the physical run while in flight (continues regardless of active tab).
  useEffect(() => {
    if (!physRun || (physRun.status !== "queued" && physRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setPhysRun(await getRun(sessionId, physRun.id));
      } catch (e) {
        setPhysErr(String(e));
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [physRun, sessionId]);

  // Poll the cost-benefit run while in flight.
  useEffect(() => {
    if (!cbRun || (cbRun.status !== "queued" && cbRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setCbRun(await getRun(sessionId, cbRun.id));
      } catch (e) {
        setCbErr(String(e));
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [cbRun, sessionId]);

  // Poll the supply-chain run while in flight (the MRIO fetch can take a while).
  useEffect(() => {
    if (!scRun || (scRun.status !== "queued" && scRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setScRun(await getRun(sessionId, scRun.id));
      } catch (e) {
        setScErr(String(e));
      }
    }, 2000);
    return () => clearTimeout(t);
  }, [scRun, sessionId]);

  const runSupplyChain = async () => {
    setScErr(null);
    setScBusy(true);
    setScRun(null);
    try {
      setScRun(await submitSupplyChain(sessionId));
    } catch (e) {
      setScErr(String(e));
    } finally {
      setScBusy(false);
    }
  };

  // Poll the calibration run while in flight.
  useEffect(() => {
    if (!calRun || (calRun.status !== "queued" && calRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setCalRun(await getRun(sessionId, calRun.id));
      } catch (e) {
        setCalErr(String(e));
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [calRun, sessionId]);

  const runCalibration = async () => {
    setCalErr(null);
    setCalBusy(true);
    setCalRun(null);
    try {
      setCalRun(await submitCalibration(sessionId));
    } catch (e) {
      setCalErr(String(e));
    } finally {
      setCalBusy(false);
    }
  };

  // Poll the forecast run while in flight (the ECMWF fetch can take a while).
  useEffect(() => {
    if (!fcRun || (fcRun.status !== "queued" && fcRun.status !== "running")) return;
    const t = setTimeout(async () => {
      try {
        setFcRun(await getRun(sessionId, fcRun.id));
      } catch (e) {
        setFcErr(String(e));
      }
    }, 2000);
    return () => clearTimeout(t);
  }, [fcRun, sessionId]);

  const runForecast = async () => {
    setFcErr(null);
    setFcBusy(true);
    setFcRun(null);
    try {
      setFcRun(await submitForecast(sessionId));
    } catch (e) {
      setFcErr(String(e));
    } finally {
      setFcBusy(false);
    }
  };

  const runPhysical = async () => {
    setPhysErr(null);
    setPhysBusy(true);
    setTransition(null);
    try {
      const [r, t] = await Promise.all([submitRun(sessionId), submitTransition(sessionId)]);
      setPhysRun(r);
      setTransition(t);
    } catch (e) {
      setPhysErr(String(e));
    } finally {
      setPhysBusy(false);
    }
  };

  const runCostBenefit = async () => {
    setCbErr(null);
    setCbBusy(true);
    setCbRun(null);
    try {
      setCbRun(await submitCostBenefit(sessionId, cbMeasures));
    } catch (e) {
      setCbErr(String(e));
    } finally {
      setCbBusy(false);
    }
  };

  const runUncertainty = async () => {
    setUncErr(null);
    setUncBusy(true);
    setUncRun(null);
    try {
      setUncRun(await submitUncertainty(sessionId, 16));
    } catch (e) {
      setUncErr(String(e));
    } finally {
      setUncBusy(false);
    }
  };

  const runLitpop = async (country: string, source = "litpop", peril = "tropical_cyclone") => {
    setLitpopErr(null);
    setLitpopBusy(true);
    setLitpopRun(null);
    try {
      setLitpopRun(await submitLitPop(sessionId, country, source, peril));
    } catch (e) {
      setLitpopErr(String(e));
    } finally {
      setLitpopBusy(false);
    }
  };

  return {
    physRun,
    transition,
    physBusy,
    physErr,
    runPhysical,
    cbRun,
    cbMeasures,
    setCbMeasures,
    cbBusy,
    cbErr,
    runCostBenefit,
    uncRun,
    uncBusy,
    uncErr,
    runUncertainty,
    litpopRun,
    litpopBusy,
    litpopErr,
    runLitpop,
    scRun,
    scBusy,
    scErr,
    runSupplyChain,
    calRun,
    calBusy,
    calErr,
    runCalibration,
    fcRun,
    fcBusy,
    fcErr,
    runForecast,
  };
}
