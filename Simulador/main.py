"""
demo.py
-------
Interface CLI de demonstração do simulador.

Simula um ciclo de quest completo:
  - Cria perfil de investidor
  - Deposita aporte mensal
  - Permite operações de compra/venda
  - Avança ciclos e exibe resultados narrativos
  - Mostra snapshot final com métricas para o agente

Execute com:  python -m simulator.demo
"""

from __future__ import annotations
import sys
import os

# Adiciona o diretório raiz ao path para permitir execução direta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.Simulator.engine import SimulatorEngine
from src.Simulator.portfolio import InvestorProfile
from src.Simulator.fixed_income import FixedIncomeType
import json
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Helpers de exibição
# ---------------------------------------------------------------------------

def print_header(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def print_market(engine: SimulatorEngine):
    snap = engine.market_snapshot()
    m = snap["market"]
    print_header("ESTADO DO MERCADO")
    print(f"  SELIC:    {m['selic_annual_pct']:.2f}% a.a.  ({m['selic_monthly_pct']:.4f}% a.m.)")
    print(f"  CDI:      {m['cdi_annual_pct']:.2f}% a.a.")
    print(f"  Inflacao: ~{m['inflation_annual_pct']:.1f}% a.a.")

    print("\n  -- Acoes --")
    print(f"  {'Ticker':<8} {'Nome':<25} {'Preco':>8} {'Var%':>7}  Trend")
    print(f"  {'─'*8} {'─'*25} {'─'*8} {'─'*7}  {'─'*15}")
    for t, s in snap["stocks"].items():
        var = s["change_pct"]
        arrow = "^" if var > 0 else ("v" if var < 0 else "-")
        print(
            f"  {s['ticker']:<8} {s['name']:<25} "
            f"R${s['price']:>6.2f}  {arrow}{abs(var):>5.1f}%  {s['trend']}"
        )

    print("\n  -- Renda Fixa --")
    for pt, p in snap["fixed_products"].items():
        maturity = f"{p['maturity_months']}m" if p["maturity_months"] > 0 else "livre"
        ir_tag = "* IR Isento" if p["ir_exempt"] else ""
        print(
            f"  [{p['label']:<22}]  {p['description'][:45]:<45}  "
            f"min: R${p['min_investment']:.0f}  prazo: {maturity}  {ir_tag}"
        )


def print_portfolio(engine: SimulatorEngine, portfolio):
    snap = engine.snapshot(portfolio)
    print_header(f"PORTFOLIO — Ciclo {snap['cycle']}")
    print(f"  Patrimonio Liquido:  R$ {snap['net_worth']:,.2f}")
    print(f"  Caixa disponivel:    R$ {snap['cash']:,.2f}")

    alloc = snap["allocation"]
    print(
        f"  Alocacao:  Caixa {alloc['cash_pct']}%  |  "
        f"Renda Fixa {alloc['fixed_pct']}%  |  "
        f"Acoes {alloc['stocks_pct']}%"
    )

    ef = snap["emergency_fund"]
    status = "[OK]" if ef["adequate"] else "[ATENCAO]"
    print(
        f"\n  {status} Reserva de Emergencia: "
        f"R$ {ef['liquid_assets']:,.2f} / R$ {ef['target']:,.2f} "
        f"({ef['completion_pct']}%)"
    )

    gp = snap["goal_progress"]
    achieved = "[META ATINGIDA]" if gp["achieved"] else "[META]"
    print(
        f"  {achieved} Objetivo [{gp['goal']}]: "
        f"R$ {gp['current_net_worth']:,.2f} / R$ {gp['goal_amount']:,.2f} "
        f"({gp['completion_pct']}%)"
    )

    if snap["fixed_positions"]:
        print("\n  -- Renda Fixa --")
        for i, p in enumerate(snap["fixed_positions"]):
            liquid = "[liquido]" if p["can_redeem"] else f"[bloqueado {p['months_held']}m]"
            print(
                f"  [{i}] {p['product']:<22}  "
                f"R$ {p['principal_with_earnings']:,.2f}  "
                f"(+R$ {p['gross_earnings']:.2f} bruto)  "
                f"liquido: R$ {p['net_redemption_value']:,.2f}  {liquid}"
            )

    if snap["stock_positions"]:
        print("\n  -- Acoes --")
        for p in snap["stock_positions"]:
            pnl_sign = "+" if p["unrealized_pnl"] >= 0 else ""
            print(
                f"  {p['ticker']:<8}  {p['shares']:.4f} acoes  "
                f"P.medio: R${p['avg_purchase_price']:.2f}  "
                f"Atual: R${p['current_price']:.2f}  "
                f"Valor: R${p['current_value']:,.2f}  "
                f"P&L: {pnl_sign}R${p['unrealized_pnl']:.2f} ({pnl_sign}{p['unrealized_pnl_pct']}%)"
            )


# ---------------------------------------------------------------------------
# Cenário de demonstração
# ---------------------------------------------------------------------------

def run_demo():
    print("\n" + "="*60)
    print("  SIMULADOR DE INVESTIMENTOS — MVP Demo")
    print("  Plataforma de Educacao Financeira")
    print("="*60)

    # -- 1. Criar engine e perfil --
    engine = SimulatorEngine(seed=42)

    profile = InvestorProfile(
        user_id="demo-user-001",
        name="Aldric, o Aprendiz",
        monthly_income=5000.0,
        monthly_expenses=3000.0,
        risk_profile="moderado",
        knowledge_level="iniciante",
        goal="Reserva de emergencia de 6 meses",
        goal_amount=18_000.0,
        goal_deadline_months=24,
    )

    portfolio = engine.create_portfolio(profile, initial_cash=0.0)
    print(f"\n  Personagem criado: {profile.name}")
    print(f"  Renda mensal: R$ {profile.monthly_income:,.2f}")
    print(f"  Gastos fixos: R$ {profile.monthly_expenses:,.2f}")
    print(f"  Sobra mensal: R$ {profile.monthly_surplus:,.2f}")
    print(f"  Objetivo: {profile.goal} (R$ {profile.goal_amount:,.2f})")
    print(f"  Prazo: {profile.goal_deadline_months} meses")
    print(f"  Reserva ideal: R$ {profile.recommended_emergency_fund:,.2f}")

    # -- 2. Estado inicial do mercado --
    print_market(engine)

    # -- 3. Quest: "Monte sua reserva de emergência" --
    print_header("QUEST ATIVA: Monte sua Reserva de Emergencia")
    print(
        "  Objetivo: Acumular R$ 18.000 em ativos liquidos em 12 meses.\n"
        "  Dica do Sabio: 'O Tesouro Selic garante liquidez e seguranca.'\n"
        "  O aventureiro Aldric recebe seu primeiro salario..."
    )

    # -- 4. Ciclo 1: deposito + alocacao inicial --
    engine.deposit(portfolio, profile.monthly_surplus, "Aporte inicial")
    print(f"\n  Deposito: R$ {profile.monthly_surplus:,.2f} no caixa")

    engine.buy_fixed(portfolio, FixedIncomeType.TESOURO_SELIC, 1000.0)
    print("  Comprou R$ 1.000 em Tesouro Selic")

    engine.buy_fixed(portfolio, FixedIncomeType.CDB_DAILY, 500.0)
    print("  Comprou R$ 500 em CDB Liquidez Diaria")

    # Tambem compra algumas acoes para demonstrar renda variavel (sobram R$500)
    engine.buy_stock(portfolio, "BRCO3", 300.0)
    print("  Comprou R$ 300 em BRCO3 (Banco do Reinos)")

    engine.buy_stock(portfolio, "TCNV5", 150.0)
    print("  Comprou R$ 150 em TCNV5 (TecnoVentos - alta volatilidade)")

    print_portfolio(engine, portfolio)

    # -- 5. Simular 6 ciclos (6 meses) com aportes mensais --
    print_header("AVANCANDO 6 MESES SIMULADOS...")

    for i in range(6):
        result = engine.advance_cycle()
        print(engine.narrative_cycle_summary(result))

        # Deposito mensal automatico
        engine.deposit(portfolio, profile.monthly_surplus, f"Aporte mes {result.cycle}")

        # Estrategia simples: investir toda a sobra em Tesouro Selic
        if portfolio.cash >= 1000:
            to_invest = round(portfolio.cash * 0.8, 2)  # deixa 20% em caixa
            if to_invest >= 100:
                engine.buy_fixed(portfolio, FixedIncomeType.TESOURO_SELIC, to_invest)
                print(f"  Reinvestiu R$ {to_invest:,.2f} em Tesouro Selic")

        # No mes 3: compra um pouco de LCA para demonstrar produto com carencia
        if result.cycle == 3 and portfolio.cash >= 5000:
            engine.buy_fixed(portfolio, FixedIncomeType.LCA_1Y, 5000.0)
            print("  Comprou R$ 5.000 em LCA 1 ano (isento de IR)")

    # -- 6. Estado final --
    print_market(engine)
    print_portfolio(engine, portfolio)

    # -- 7. Snapshot para o agente de IA --
    print_header("DADOS PARA O AGENTE DE IA (JSON)")
    snap = engine.snapshot(portfolio)
    # Exibe apenas os campos relevantes para geracao de quest
    agent_context = {
        "cycle": snap["cycle"],
        "net_worth": snap["net_worth"],
        "allocation": snap["allocation"],
        "emergency_fund": snap["emergency_fund"],
        "goal_progress": snap["goal_progress"],
        "market_selic": snap["market"]["selic_annual_pct"],
        "open_positions": len(snap["fixed_positions"]) + len(snap["stock_positions"]),
    }
    print(json.dumps(agent_context, indent=2, ensure_ascii=False))

    # -- 8. Demonstracao de falha de quest (saque indevido) --
    print_header("DEMO: Tentativa de resgate com carencia")

    # Compra um CDB de 90 dias para demonstrar a carencia
    engine.deposit(portfolio, 1000.0, "Deposito para demo de carencia")
    engine.buy_fixed(portfolio, FixedIncomeType.CDB_90, 1000.0)
    print(f"  Comprou R$ 1.000 em CDB 90 dias (carencia de 3 meses)")
    print(f"  Ciclo atual: {engine.market.cycle} — carencia termina no ciclo {engine.market.cycle + 3}")
    print("  Tentando resgatar imediatamente...\n")

    try:
        cdb_idx = next(
            i for i, p in enumerate(portfolio.fixed_positions)
            if not p.can_redeem(engine.market.cycle)
        )
        engine.redeem_fixed(portfolio, cdb_idx)
        print("  [ERRO] Deveria ter bloqueado o resgate!")
    except ValueError as e:
        print(f"  Operacao bloqueada corretamente: {e}")
        print("  Conceito educativo: produtos com carencia nao podem ser")
        print("  resgatados antes do vencimento — planejamento e essencial!")

    print("\n" + "="*60)
    print("  Demo concluida com sucesso!")
    print("  O simulador esta pronto para integracao com o agente de IA")
    print("  e com o sistema de quests do MVP.")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_demo()
