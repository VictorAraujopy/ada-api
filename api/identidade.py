"""Quem é quem pela origem da requisição: IPs do Victor = victor, IPs do convidado = convidado, resto = visitante.
Os IPs vêm do .env do core (ADA_IPS_VICTOR / ADA_IPS_CONVIDADO), sem login: a tailnet é o portão."""
import os

from fastapi import Request

from api import config


def _ips(var):
    return {ip.strip() for ip in os.environ.get(var, "").split(",") if ip.strip()}


# config.HOST é o IP que o PRÓPRIO servidor escuta: requisição da máquina pra ela mesma = Victor
IPS_VICTOR = {"127.0.0.1", "::1", config.HOST} | _ips("ADA_IPS_VICTOR")
IPS_CONVIDADO = _ips("ADA_IPS_CONVIDADO") - IPS_VICTOR


def usuario_de(req: Request) -> str:
    ip = req.client.host if req.client else ""
    if ip in IPS_VICTOR:
        return "victor"
    return "convidado" if ip in IPS_CONVIDADO else "visitante"
