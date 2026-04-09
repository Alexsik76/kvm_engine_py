package auth

import (
	"errors"
	"fmt"

	"github.com/golang-jwt/jwt/v5"
)

// ValidateAccessToken verifies the JWT token and returns the subject (user ID)
func ValidateAccessToken(tokenString string, secret string) (string, error) {
	token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
		// Ensure the signing method is HMAC
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(secret), nil
	})

	if err != nil {
		return "", err
	}

	if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
		// Ensure the type claim exists and equals "access"
		tokenType, ok := claims["type"].(string)
		if !ok || tokenType != "access" {
			return "", errors.New("invalid token type")
		}

		// Ensure the sub claim exists
		sub, ok := claims["sub"].(string)
		if !ok || sub == "" {
			return "", errors.New("subject (sub) claim missing")
		}

		return sub, nil
	}

	return "", errors.New("invalid token")
}
