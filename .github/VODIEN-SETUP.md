# Connect GitHub to the live Salon Ten website

Jeremy does this once. After the first successful upload, Kel can ask her Claude to edit this
repository and push to `main`; the live Vodien site should normally update within a couple of
minutes. The workflow must be published to GitHub before steps 10 and 11 are available.

1. Open the same Vodien cPanel you used for the website upload.
2. Under **Files**, click **FTP Accounts**.
3. Under **Add FTP Account**, enter `github-deploy` in **Log In** and select `salonten.com.au`
   in **Domain**.
4. Use **Password Generator**, save the generated password in your password manager, and fill
   **Password** and **Password (Again)** with it.
5. Set **Directory** to `public_html`. Remove any automatically added domain or username
   subfolder. If cPanel shows a fixed `/home/your-cpanel-user/` prefix, leave that prefix alone;
   the complete directory must be `/home/your-cpanel-user/public_html`.
6. Select **Unlimited** for **Quota** if that option appears, then click **Create FTP Account**.
7. Beside the new account, click **Configure FTP Client** and copy the full **FTP Username**,
   normally `github-deploy@salonten.com.au`. For the server, use the hosting server's actual
   hostname from Vodien's hosting details or **Account Manager > Email Notifications > Your
   Web Hosting is Ready**. Encrypted FTP needs the hostname covered by the server certificate;
   do not assume `ftp.salonten.com.au` is that hostname. [Vodien credentials guide](https://www.vodien.com/help/article/ftp-login-credentials),
   [cPanel FTP guide](https://docs.cpanel.net/cpanel/files/ftp-accounts/).
8. Open https://github.com/jeremy-andreani/salon-ten-site. Click **Settings**, then **Secrets
   and variables**, then **Actions**.
9. Click **New repository secret** for each row below. Enter its **Name** and **Secret**, then
   click **Add secret**. Repeat until all three appear. [GitHub secrets guide](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

   | Name | Secret |
   | --- | --- |
   | `VODIEN_FTP_SERVER` | The hosting server hostname from step 7, with no `ftp://`, `https://`, port or folder path |
   | `VODIEN_FTP_USERNAME` | The full FTP username copied in step 7 |
   | `VODIEN_FTP_PASSWORD` | The password generated in step 4 |

10. Click **Actions**, select **Deploy to Vodien**, click **Run workflow**, leave **Branch**
    as `main`, then click the green **Run workflow** button. Adding secrets alone does not
    start an upload.
11. Open that run and wait for a green tick. Then open https://salonten.com.au/ and a treatment
    page, check **Book Now**, and check that https://salonten.com.au/contact/ redirects to
    `contact.html`. If the run is red, open its failed step to see the error.

The account-specific server hostname could not be verified during preparation. Vodien's public
guides do not provide one universal hostname to substitute. Use the exact hostname assigned to
this hosting account; the workflow uses explicit FTPS on port 21 and checks the certificate.

Because this account is restricted to `public_html`, its FTP root `./` is already that folder.
The workflow deliberately uses `server-dir: ./`; `public_html/` would create an extra nested
folder and leave the real website unchanged.

The first upload sends all public website files and creates `.salon-ten-vodien-sync-state.json`.
Later uploads compare with that state and send changed files. Keep that state file. The workflow
does not use clean-slate deletion and excludes `old-wordpress/`, `cgi-bin/`, `.well-known/`, and
`new-site-test/` from uploads and deletions. Repository notes, configuration, screenshots and the
landing-page template are excluded too. A deliberately removed previously deployed site file
may be removed on the next sync; the four protected folders remain excluded.

GitHub Pages settings are unchanged. Once the Vodien connection is proven, retiring the old
preview is recommended so Kel has only one site to check. Disabling it is a separate decision;
this setup does not change Pages, hosting or DNS settings.

Technical reference: [FTP Deploy Action v4.4.0](https://github.com/SamKirkland/FTP-Deploy-Action/releases/tag/v4.4.0).
