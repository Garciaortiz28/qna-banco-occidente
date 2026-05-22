"""
email_service.py — Servicio de correo electrónico con Resend
Envía email de bienvenida personalizado a nuevos usuarios.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_welcome_html(nombre: str, email: str) -> str:
    """Genera el HTML del email de bienvenida con branding del banco."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bienvenido al Asistente Virtual</title>
</head>
<body style="margin:0;padding:0;background:#F4F7FB;font-family:Inter,Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#F4F7FB;padding:40px 20px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table width="560" cellpadding="0" cellspacing="0"
               style="background:white;border-radius:16px;
                      box-shadow:0 4px 20px rgba(0,90,180,.1);
                      overflow:hidden;max-width:100%;">

          <!-- Header azul -->
          <tr>
            <td style="background:linear-gradient(135deg,#003DA5,#001E55);
                       padding:32px 40px;text-align:center;">
              <h1 style="color:white;font-size:24px;margin:0 0 4px 0;
                         font-family:Georgia,serif;font-weight:700;">
                Banco de Occidente
              </h1>
              <p style="color:rgba(255,255,255,.8);font-size:14px;margin:0;">
                Asistente Virtual Inteligente
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px;">
              <p style="color:#1A2332;font-size:22px;font-weight:700;margin:0 0 8px 0;">
                ¡Hola, {nombre}! 👋
              </p>
              <p style="color:#2E4057;font-size:15px;line-height:1.7;margin:0 0 20px 0;">
                Bienvenido al Asistente Virtual del
                <strong style="color:#003DA5;">Banco de Occidente</strong>.
                Tu cuenta ha sido activada y ya puedes comenzar a usar
                todos los servicios disponibles.
              </p>

              <!-- Servicios -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background:#F0F8FE;border-radius:12px;
                            border:1px solid #E0EEF8;padding:20px;
                            margin-bottom:24px;">
                <tr>
                  <td>
                    <p style="color:#003DA5;font-size:13px;font-weight:700;
                               text-transform:uppercase;letter-spacing:1px;
                               margin:0 0 14px 0;">
                      Lo que puedes hacer:
                    </p>
                    <p style="color:#2E4057;font-size:14px;margin:0 0 8px 0;">
                      💳 Consultar productos: tarjetas, créditos, cuentas
                    </p>
                    <p style="color:#2E4057;font-size:14px;margin:0 0 8px 0;">
                      📍 Encontrar sucursales y horarios de atención
                    </p>
                    <p style="color:#2E4057;font-size:14px;margin:0 0 8px 0;">
                      📞 Obtener líneas de atención al cliente
                    </p>
                    <p style="color:#2E4057;font-size:14px;margin:0;">
                      🔒 Reportar bloqueos y emergencias bancarias
                    </p>
                  </td>
                </tr>
              </table>

              <!-- Nota memoria -->
              <div style="border-left:3px solid #0078C8;padding:12px 16px;
                          background:#F0F5FB;border-radius:0 8px 8px 0;
                          margin-bottom:24px;">
                <p style="color:#2E4057;font-size:14px;margin:0;line-height:1.6;">
                  💾 <strong>Tu conversación se guarda automáticamente.</strong>
                  La próxima vez que accedas, podrás continuar exactamente
                  donde lo dejaste.
                </p>
              </div>

              <!-- CTA -->
              <div style="text-align:center;margin-bottom:8px;">
                <a href="https://TU_URL_DE_DEPLOY_AQUI"
                   style="background:linear-gradient(135deg,#0078C8,#003DA5);
                          color:white;text-decoration:none;font-size:15px;
                          font-weight:700;padding:14px 32px;border-radius:50px;
                          display:inline-block;
                          box-shadow:0 4px 16px rgba(0,120,200,.35);">
                  Abrir Asistente Virtual
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#F4F7FB;padding:20px 40px;
                       border-top:1px solid #E0EEF8;text-align:center;">
              <p style="color:#5A7290;font-size:12px;margin:0 0 4px 0;">
                Este correo fue enviado a <strong>{email}</strong> porque
                te registraste en el Asistente Virtual del Banco de Occidente.
              </p>
              <p style="color:#94A3B8;font-size:11px;margin:0;">
                © 2026 Banco de Occidente · Sistema académico UAO
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
"""


def send_welcome_email(email: str, nombre: str) -> bool:
    """
    Envía el email de bienvenida a un nuevo usuario.

    Args:
        email: Dirección del destinatario
        nombre: Nombre del usuario (para personalización)

    Returns:
        True si se envió correctamente, False si hubo error
    """
    try:
        import resend

        resend.api_key = os.getenv("RESEND_API_KEY", "")
        email_from     = os.getenv("EMAIL_FROM", "onboarding@resend.dev")

        if not resend.api_key:
            print("[email] RESEND_API_KEY no configurado. Omitiendo email.")
            return False

        response = resend.Emails.send({
            "from":    email_from,
            "to":      email,
            "subject": "Bienvenido al Asistente Virtual del Banco de Occidente",
            "html":    _get_welcome_html(nombre, email),
        })

        print(f"[email] Email de bienvenida enviado a {email} | ID: {response.get('id')}")
        return True

    except Exception as e:
        # No romper el flujo si el email falla
        print(f"[email] Error enviando bienvenida a {email}: {e}")
        return False
