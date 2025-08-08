/**
 * Exempel på klientkod för säker token-hantering
 * 
 * Detta exempel visar hur man:
 * 1. Ansluter till WebSocket-servern med Authorization header
 * 2. Kontrollerar NTP-synkronisering
 * 3. Hanterar kortlivade access tokens och refresh flow
 * 4. Validerar token expiry lokalt innan användning
 */

// Token-hantering
class TokenManager {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = 0;
    this.tokenType = 'Bearer';
    this.userId = null;
    this.serverTimeOffset = 0; // För att hantera NTP-drift
  }

  /**
   * Hämta en ny token från servern
   */
  async requestNewToken() {
    // Anslut till Socket.IO utan autentisering först
    const socket = io('http://localhost:8000', { 
      autoConnect: true,
      reconnection: true,
      path: '/socket.io'
    });

    return new Promise((resolve, reject) => {
      // Lyssna på anslutningshändelse
      socket.on('connect', () => {
        console.log('Ansluten för att begära token');

        // Begär token
        socket.emit('request_token', {
          user_id: 'frontend_client',
          scope: 'read',
          expiry_minutes: 15
        });
      });

      // Lyssna på token-svar
      socket.on('token_generated', (response) => {
        console.log('Token mottagen');
        this.setTokens(response);
        
        // Synka klock-offset med servern
        this.syncServerTime();
        
        socket.disconnect();
        resolve(response);
      });

      // Lyssna på fel
      socket.on('token_error', (error) => {
        console.error('Fel vid begäran av token:', error);
        socket.disconnect();
        reject(error);
      });

      // Timeout efter 10 sekunder
      setTimeout(() => {
        socket.disconnect();
        reject(new Error('Timeout vid begäran av token'));
      }, 10000);
    });
  }

  /**
   * Använd refresh token för att få en ny access token
   */
  async refreshAccessToken() {
    if (!this.refreshToken) {
      throw new Error('Ingen refresh token tillgänglig');
    }

    // Anslut till Socket.IO utan autentisering för token-förnyelse
    const socket = io('http://localhost:8000', {
      autoConnect: true,
      reconnection: true,
      path: '/socket.io'
    });

    return new Promise((resolve, reject) => {
      socket.on('connect', () => {
        console.log('Ansluten för att förnya token');

        // Begär token-förnyelse
        socket.emit('refresh_token', {
          refresh_token: this.refreshToken
        });
      });

      // Lyssna på förnyelsesvar
      socket.on('token_refreshed', (response) => {
        console.log('Token förnyad');
        
        // Uppdatera endast access token, behåll refresh token
        this.accessToken = response.access_token;
        this.expiresAt = Date.now() + (response.expires_in * 1000);
        this.tokenType = response.token_type || 'Bearer';
        
        socket.disconnect();
        resolve(response);
      });

      // Lyssna på fel
      socket.on('token_error', (error) => {
        console.error('Fel vid förnyelse av token:', error);
        socket.disconnect();
        
        // Vid fel med refresh token, begär ny komplett token
        this.requestNewToken()
          .then(resolve)
          .catch(reject);
      });

      // Timeout efter 10 sekunder
      setTimeout(() => {
        socket.disconnect();
        reject(new Error('Timeout vid förnyelse av token'));
      }, 10000);
    });
  }

  /**
   * Lagra token-information
   */
  setTokens(tokenData) {
    this.accessToken = tokenData.access_token;
    this.refreshToken = tokenData.refresh_token;
    this.expiresAt = Date.now() + (tokenData.expires_in * 1000);
    this.tokenType = tokenData.token_type || 'Bearer';
    this.userId = tokenData.user_id;

    // Spara tokens i localStorage (endast för utveckling, använd mer säkra metoder i produktion)
    localStorage.setItem('auth_tokens', JSON.stringify({
      accessToken: this.accessToken,
      refreshToken: this.refreshToken,
      expiresAt: this.expiresAt,
      tokenType: this.tokenType,
      userId: this.userId
    }));
  }

  /**
   * Ladda tokens från lagring
   */
  loadTokens() {
    const savedTokens = localStorage.getItem('auth_tokens');
    if (savedTokens) {
      const tokenData = JSON.parse(savedTokens);
      this.accessToken = tokenData.accessToken;
      this.refreshToken = tokenData.refreshToken;
      this.expiresAt = tokenData.expiresAt;
      this.tokenType = tokenData.tokenType || 'Bearer';
      this.userId = tokenData.userId;
      return true;
    }
    return false;
  }

  /**
   * Kontrollera om access token har gått ut eller är nära att gå ut
   */
  isTokenExpired(bufferSeconds = 60) {
    const now = Date.now();
    // Lägg till buffert för att förnya i förväg
    return !this.accessToken || (now + (bufferSeconds * 1000)) >= this.expiresAt;
  }

  /**
   * Få giltig access token, förnya om nödvändigt
   */
  async getValidAccessToken() {
    if (this.isTokenExpired()) {
      if (this.refreshToken) {
        try {
          await this.refreshAccessToken();
        } catch (error) {
          // Om förnyelse misslyckas, begär en helt ny token
          await this.requestNewToken();
        }
      } else {
        await this.requestNewToken();
      }
    }
    return this.accessToken;
  }

  /**
   * Synkronisera lokal tid med servern för att hantera NTP-drift
   */
  async syncServerTime() {
    try {
      // Skicka en enkel begäran för att hämta server-tid
      const startTime = Date.now();
      const response = await fetch('http://localhost:8000/time');
      const endTime = Date.now();
      const roundTripTime = endTime - startTime;
      
      const data = await response.json();
      const serverTime = data.timestamp * 1000; // Konvertera sekunder till millisekunder
      
      // Beräkna ungefärlig offset med hänsyn till nätverksfördröjning
      // Antar att nätverksfördröjningen är ungefär samma i båda riktningar
      const approximateOffset = serverTime - (startTime + Math.floor(roundTripTime / 2));
      
      this.serverTimeOffset = approximateOffset;
      console.log(`Server time offset: ${approximateOffset}ms`);
      
    } catch (error) {
      console.error('Kunde inte synka tid med servern:', error);
    }
  }
  
  /**
   * Få justerad lokal tid (med server-offset)
   */
  getAdjustedTime() {
    return Date.now() + this.serverTimeOffset;
  }
  
  /**
   * Logga ut och rensa tokens
   */
  logout() {
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = 0;
    this.userId = null;
    localStorage.removeItem('auth_tokens');
  }
}

// Användning
const tokenManager = new TokenManager();

// Anslut till WebSocket med autentisering
async function connectToWebSocket() {
  try {
    // Försök ladda tidigare tokens
    if (!tokenManager.loadTokens() || tokenManager.isTokenExpired()) {
      await tokenManager.getValidAccessToken();
    }
    
    // Synka tid med servern för att undvika NTP-drift
    await tokenManager.syncServerTime();
    
    // Anslut med token i Authorization-header
    const socket = io('http://localhost:8000', {
      autoConnect: true,
      reconnection: true,
      path: '/socket.io',
      extraHeaders: {
        'Authorization': `Bearer ${tokenManager.accessToken}`
      }
    });
    
    // Lyssna på händelser
    socket.on('connect', () => {
      console.log('Ansluten till WebSocket med autentisering');
    });
    
    socket.on('connect_error', async (error) => {
      console.error('Anslutningsfel:', error);
      
      // Om anslutningen misslyckas p.g.a. autentisering, försök förnya token
      if (error.message.includes('Authentication')) {
        console.log('Förnyar token och försöker ansluta igen...');
        await tokenManager.getValidAccessToken();
        socket.disconnect().connect(); // Koppla från och anslut igen med ny token
      }
    });
    
    // Automatisk förnyelse av token innan den går ut
    setInterval(async () => {
      if (tokenManager.isTokenExpired(300)) { // Förnya 5 minuter innan utgång
        console.log('Förnyar token proaktivt...');
        await tokenManager.getValidAccessToken();
      }
    }, 60000); // Kontrollera varje minut
    
    return socket;
  } catch (error) {
    console.error('Fel vid anslutning:', error);
    throw error;
  }
}

// Exportera för användning i applikationen
window.tokenManager = tokenManager;
window.connectToWebSocket = connectToWebSocket;
